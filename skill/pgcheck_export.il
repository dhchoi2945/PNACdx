; PGCHECK Phase 0 connectivity exporter, source-session DB snapshot.
; Load pgcheck_json.il first. Public entry:
;   pgcExport("allowedLib" "PGC_T01_TOP" "schematic" "/new/run-dir" "run-001")
;
; ONLY dbOpenCellViewByType(... nil "r") is used. This file never saves,
; checks, edits, deletes, flattens, or rebinds source database objects.
; Read mode can return an already-open in-memory CV: saved/check state is
; explicitly unverified. No Config/HDB or simulator binding is claimed.
; Target runtime IC25.1-64b.SM_ISR7.10: NOT_TESTED outside the internal site.

procedure(pgcENext(ctx prefix)
  ctx['serial]=ctx['serial]+1
  sprintf(nil "%s-%d" prefix ctx['serial])
)

procedure(pgcEWrite(ctx kind row)
  pgcJWriteLine(ctx[kind] row)
  ctx['counts][kind]=ctx['counts][kind]+1
)

procedure(pgcEIssue(ctx path code message objectId)
  pgcEWrite(ctx 'unresolved pgcJObject(list(
    list("id" pgcJString(pgcENext(ctx "u")))
    list("path" pgcJString(path))
    list("code" pgcJString(code))
    list("message" pgcJString(message))
    list("severity" pgcJString("error"))
    list("object_id" pgcJNullableString(objectId))
  )))
)

procedure(pgcEWarning(ctx path code message)
  ctx['warnings]=cons(pgcJObject(list(
    list("path" pgcJString(path)) list("code" pgcJString(code))
    list("message" pgcJString(message))
  )) ctx['warnings])
)

; Return errset's one-element success envelope. (nil) means an observed nil;
; nil means failed inspection. Callers must retain that distinction.
procedure(pgcEGet(ctx obj attr path objectId)
  prog((answer attributes)
    attributes=errset(obj~>? t)
    unless(attributes &&
      (member(attr car(attributes)) || member(symbolToString(attr) car(attributes)))
      pgcEIssue(ctx path "DB_ATTRIBUTE_UNAVAILABLE"
        sprintf(nil "Required DB attribute %L is unavailable; inspect pgcEGet." attr) objectId)
      return(nil)
    )
    answer=errset(dbGet(obj attr) t)
    unless(answer
      pgcEIssue(ctx path "DB_READ_FAILED"
        sprintf(nil "Failed to read DB attribute %L; see internal CIW diagnostic." attr) objectId)
    )
    return(answer)
  )
)

procedure(pgcERequiredString(ctx obj attr path objectId)
  let((answer)
    answer=pgcEGet(ctx obj attr path objectId)
    if(answer && stringp(car(answer)) && strlen(car(answer))>0 then car(answer)
    else
      pgcEIssue(ctx path "DB_STRING_INVALID"
        sprintf(nil "Missing/nonstring/empty required attribute %L." attr) objectId)
      pgcENext(ctx "@invalid")
    )
  )
)

procedure(pgcEList(ctx obj attr path objectId)
  let((answer)
    answer=pgcEGet(ctx obj attr path objectId)
    if(answer && listp(car(answer)) then car(answer)
    else
      when(answer pgcEIssue(ctx path "DB_LIST_INVALID"
        sprintf(nil "Required collection %L is not a list." attr) objectId))
      nil
    )
  )
)

procedure(pgcEView(libraryName cellName viewName)
  pgcJObject(list(list("library" pgcJString(libraryName))
    list("cell" pgcJString(cellName)) list("view" pgcJString(viewName))))
)

procedure(pgcEKey(libraryName cellName viewName)
  pgcJPathAppend(pgcJPathAppend(pgcJPathAppend("" libraryName) cellName) viewName)
)

procedure(pgcEUnsupportedName(name)
  ; These spellings are conservatively rejected, never expanded/merged.
  cond((index(name "!") "GLOBAL_NET_UNSUPPORTED")
       ((index(name "<") || index(name ">") || index(name "[") || index(name "]"))
        "BUS_OR_ARRAY_UNSUPPORTED")
       (t nil))
)

; Check known inherited-connection properties without evaluating expressions.
; Missing properties are an observed absence; failed API calls are errors.
procedure(pgcECheckExpressions(ctx obj path objectId)
  let((answer found props typeAnswer)
    found=nil
    foreach(propName '("netExpr" "netSet")
      answer=errset(dbFindProp(obj propName) t)
      if(answer then
        when(car(answer)
          found=t
          pgcEIssue(ctx path "INHERITED_CONNECTION_UNSUPPORTED"
            sprintf(nil "Property %s exists; inherited expression resolution is unsupported." propName)
            objectId)
        )
      else
        found=t
        pgcEIssue(ctx path "EXPRESSION_INSPECTION_FAILED"
          sprintf(nil "dbFindProp(%s) failed; inherited connections cannot be excluded." propName)
          objectId)
      )
    )
    ; A netSet property's *name* can be arbitrary. Its valueType, rather
    ; than its name, identifies it. Never interpret/evaluate its value.
    props=pgcEGet(ctx obj 'prop path objectId)
    if(props && listp(car(props)) then
      foreach(prop car(props)
        typeAnswer=pgcEGet(ctx prop 'valueType path objectId)
        if(typeAnswer then
          when(equal(car(typeAnswer) "netSet")
            found=t
            pgcEIssue(ctx path "INHERITED_CONNECTION_UNSUPPORTED"
              "A property of valueType netSet exists; hierarchy resolution is unsupported." objectId))
        else found=t)
      )
    else
      found=t
      when(props pgcEIssue(ctx path "PROPERTY_LIST_INVALID" "DB prop collection is not a list." objectId))
    )
    found
  )
)

; Optional DB attributes are queried only when advertised by obj~>?. A
; successful absent attribute returns (nil); a failed inspection returns nil
; with a diagnostic. This is for feature screening, never connectivity.
procedure(pgcEOptionalGet(ctx obj attr path objectId)
  let((attributes answer)
    attributes=errset(obj~>? t)
    if(attributes then
      if(member(attr car(attributes)) || member(symbolToString(attr) car(attributes)) then
        answer=errset(dbGet(obj attr) t)
        unless(answer pgcEIssue(ctx path "OPTIONAL_ATTRIBUTE_READ_FAILED"
          sprintf(nil "Advertised optional attribute %L failed to read." attr) objectId))
        answer
      else list(nil))
    else
      pgcEIssue(ctx path "OPTIONAL_ATTRIBUTE_INSPECTION_FAILED"
        sprintf(nil "Cannot inspect optional attribute %L." attr) objectId)
      nil
    )
  )
)

; Read-only screening, not a resolver. These public APIs are shown in
; Cadence's community examples, but target-version support is probed at run
; time. An unavailable/failed screen conservatively prevents completeness.
procedure(pgcEScreenCellView(ctx definition path)
  let((cv id answer signals flag name globals mosaics)
    cv=definition['cv] id=definition['id] globals=nil
    foreach(api '(dbGetCellViewInheritedTerm dbGetCellViewInheritedSig)
      if(isCallable(api) then
        answer=errset(apply(api list(cv)) t)
        if(answer && listp(car(answer)) then
          when(car(answer)
            definition['has_inherited]=t
            pgcEIssue(ctx path "INHERITED_CONNECTION_UNSUPPORTED"
              sprintf(nil "%L found inherited terminals/signals; no elaboration is attempted." api) id))
          if(eq(api 'dbGetCellViewInheritedTerm) then
            definition['inherited_terms]=car(answer)
          else definition['inherited_signals]=car(answer))
        else
          definition['semantic_screen_failed]=t
          pgcEIssue(ctx path "INHERITED_SCREEN_FAILED"
            sprintf(nil "%L failed or returned an invalid collection." api) id)
        )
      else
        definition['semantic_screen_failed]=t
        pgcEIssue(ctx path "INHERITED_SCREEN_UNAVAILABLE"
          sprintf(nil "%L is unavailable; verify site API before claiming complete extraction." api) id)
      )
    )
    ; In OA, global-ness is a signal property, not reliably a net property.
    signals=pgcEGet(ctx cv 'signals path id)
    if(signals && listp(car(signals)) then
      foreach(sig car(signals)
        flag=pgcEGet(ctx sig 'isGlobal path id)
        unless(flag definition['semantic_screen_failed]=t)
        when(flag && car(flag) && !(stringp(car(flag)) && equal(upperCase(car(flag)) "FALSE"))
          name=pgcERequiredString(ctx sig 'name path id)
          globals=cons(name globals)
          pgcEIssue(ctx path "GLOBAL_NET_UNSUPPORTED"
            sprintf(nil "Global signal %s is retained locally without hierarchy merging." name) id))
      )
    else
      definition['semantic_screen_failed]=t
      when(signals pgcEIssue(ctx path "SIGNAL_LIST_INVALID" "DB signals collection is not a list." id))
    )
    definition['global_names]=globals
    ; A separate collection can contain mosaics omitted by cv~>instances.
    mosaics=pgcEOptionalGet(ctx cv 'mosaics path id)
    when(mosaics && car(mosaics)
      pgcEIssue(ctx path "MOSAICS_UNSUPPORTED"
        "CellView contains mosaics; array occurrences are not expanded in Phase 0." id))
  )
)

procedure(pgcEOptionalFlag(ctx obj attr path objectId)
  prog((attributes answer)
    attributes=errset(obj~>? t)
    unless(attributes
      pgcEIssue(ctx path "SEMANTIC_INSPECTION_FAILED" "Cannot inspect optional DB attributes." objectId)
      return(t)
    )
    return(if(member(attr car(attributes)) || member(symbolToString(attr) car(attributes)) then
      answer=errset(dbGet(obj attr) t)
      if(answer then
        car(answer) && !(stringp(car(answer)) && equal(upperCase(car(answer)) "FALSE"))
      else
        pgcEIssue(ctx path "SEMANTIC_INSPECTION_FAILED"
          sprintf(nil "Optional semantic attribute %L failed to read." attr) objectId)
        t
      )
    else nil))
  )
)

procedure(pgcEPinHelper(libraryName cellName viewName)
  ; Exact built-in helper identities only. Never exclude arbitrary PDK cells.
  equal(libraryName "basic") && equal(viewName "symbol") &&
    member(cellName '("ipin" "opin" "iopin" "sympin"))
)

procedure(pgcEPlacement(ctx inst path)
  let((origin orient encoded)
    ; Placement is optional. No extraction error is emitted for its failure.
    origin=errset(inst~>xy t) orient=errset(inst~>orient t)
    encoded=nil
    when(origin && orient && listp(car(origin)) && length(car(origin))==2 &&
         numberp(caar(origin)) && numberp(cadar(origin)) && stringp(car(orient))
      encoded=errset(pgcJObject(list(
        list("x" pgcJNumber(caar(origin))) list("y" pgcJNumber(cadar(origin)))
        list("orientation" pgcJString(car(orient)))
        list("coordinate_system" pgcJString("parent_local")) list("units" "null")
      )) t)
    )
    if(encoded then
      ctx['placement_supported]=t
      car(encoded)
    else
      pgcEWarning(ctx path "PLACEMENT_UNAVAILABLE"
        "Optional xy/orient read failed or is non-finite; placement is null. Coordinate units unverified.")
      "null"
    )
  )
)

; Cell definitions are deduplicated; the nets below are descriptors only.
; Occurrence net records are emitted separately by pgcEOccurrenceNets.
procedure(pgcEDefinition(ctx libraryName cellName viewName path)
  prog((key definition cv opened id terms nets termRows netNames name direction descriptor code seen)
    key=pgcEKey(libraryName cellName viewName)
    definition=ctx['definitions][key]
    when(definition return(definition))
    opened=errset(dbOpenCellViewByType(libraryName cellName viewName nil "r") t)
    unless(opened && car(opened)
      pgcEIssue(ctx path "SELECTED_VIEW_OPEN_FAILED"
        sprintf(nil "Cannot open %s/%s/%s read-only; no fallback binding was inferred."
          libraryName cellName viewName) nil)
      return(nil)
    )
    cv=car(opened)
    ctx['opened]=cons(cv ctx['opened])
    id=pgcENext(ctx "c") definition=makeTable('pgcDefinition nil)
    definition['id]=id definition['cv]=cv definition['key]=key
    definition['view']=pgcEView(libraryName cellName viewName)
    definition['terms]=nil definition['nets]=nil
    ctx['definitions][key]=definition
    unless(equal(pgcERequiredString(ctx cv 'cellViewType path id) "schematic")
      pgcEIssue(ctx path "VIEW_TYPE_UNSUPPORTED"
        "Analysis CellView is not a schematic; Config/HDB/symbol traversal is unsupported." id)
    )
    pgcECheckExpressions(ctx cv path id)
    pgcEScreenCellView(ctx definition path)
    terms=pgcEList(ctx cv 'terminals path id) termRows=nil seen=nil
    foreach(term terms
      descriptor=makeTable('pgcTerm nil) descriptor['db]=term
      descriptor['id]=pgcENext(ctx "t")
      name=pgcERequiredString(ctx term 'name path id)
      direction=pgcERequiredString(ctx term 'direction path id)
      descriptor['name]=name descriptor['direction]=direction
      descriptor['unsupported]=pgcEUnsupportedName(name)
      when(member(term definition['inherited_terms])
        descriptor['unsupported]="INHERITED_CONNECTION_UNSUPPORTED")
      when(definition['semantic_screen_failed]
        descriptor['unsupported]="SEMANTIC_SCREEN_FAILED")
      when(definition['has_inherited]
        descriptor['unsupported]="INHERITED_CONNECTION_UNSUPPORTED")
      when(member(name seen)
        pgcEIssue(ctx path "DUPLICATE_TERMINAL_NAME" name id)
        descriptor['unsupported]="DUPLICATE_TERMINAL_NAME"
      )
      seen=cons(name seen)
      when(pgcECheckExpressions(ctx term path id) descriptor['unsupported]="INHERITED_CONNECTION_UNSUPPORTED")
      definition['terms]=cons(descriptor definition['terms])
      termRows=cons(pgcJObject(list(list("id" pgcJString(descriptor['id]))
        list("name" pgcJString(name)) list("direction" pgcJString(direction)))) termRows)
    )
    definition['terms]=reverse(definition['terms])
    nets=pgcEList(ctx cv 'nets path id) netNames=nil seen=nil
    foreach(net nets
      descriptor=makeTable('pgcNet nil) descriptor['db]=net
      name=pgcERequiredString(ctx net 'name path id)
      descriptor['name]=name descriptor['unsupported]=pgcEUnsupportedName(name)
      when(member(name definition['global_names])
        descriptor['unsupported]="GLOBAL_NET_UNSUPPORTED")
      when(member(net definition['inherited_signals])
        descriptor['unsupported]="INHERITED_CONNECTION_UNSUPPORTED")
      when(definition['semantic_screen_failed]
        descriptor['unsupported]="SEMANTIC_SCREEN_FAILED")
      when(definition['has_inherited]
        descriptor['unsupported]="INHERITED_CONNECTION_UNSUPPORTED")
      when(pgcEOptionalFlag(ctx net 'isGlobal path id)
        descriptor['unsupported]="GLOBAL_NET_UNSUPPORTED"
      )
      when(pgcECheckExpressions(ctx net path id) descriptor['unsupported]="INHERITED_CONNECTION_UNSUPPORTED")
      code=descriptor['unsupported]
      when(code pgcEIssue(ctx pgcJPathAppend(path name) code
        "Net semantics require a validated advanced resolver; only the local DB object is retained." id))
      if(member(name seen) then
        pgcEIssue(ctx path "DUPLICATE_NET_NAME" name id)
      else
        definition['nets]=cons(descriptor definition['nets])
        netNames=cons(pgcJString(name) netNames)
        seen=cons(name seen)
      )
    )
    definition['nets]=reverse(definition['nets])
    definition['instances]=pgcEList(ctx cv 'instances path id)
    pgcEWrite(ctx 'cells pgcJObject(list(
      list("id" pgcJString(id)) list("path" pgcJString(key))
      list("library" pgcJString(libraryName)) list("cell" pgcJString(cellName))
      list("view" pgcJString(viewName)) list("db_id" pgcJString(sprintf(nil "%L" cv)))
      list("terminals" pgcJArray(reverse(termRows))) list("local_net_names" pgcJArray(reverse(netNames)))
    )))
    return(definition)
  )
)

procedure(pgcEFindTerm(definition name)
  let((found)
    found=nil
    when(definition foreach(term definition['terms]
      when(equal(term['name] name) found=term)
    ))
    found
  )
)

procedure(pgcEOccurrenceNets(ctx definition occurrenceId path)
  let((mapping id entry)
    mapping=nil
    foreach(net definition['nets]
      id=pgcENext(ctx "n") entry=makeTable('pgcOccurrenceNet nil)
      entry['id]=id entry['db]=net['db] entry['name]=net['name]
      entry['unsupported]=net['unsupported] mapping=cons(entry mapping)
      pgcEWrite(ctx 'nets pgcJObject(list(
        list("id" pgcJString(id)) list("path" pgcJString(pgcJPathAppend(pgcJPathAppend(path "nets") net['name])))
        list("name" pgcJString(net['name])) list("cell_id" pgcJString(definition['id]))
        list("occurrence_id" pgcJString(occurrenceId))
      )))
    )
    reverse(mapping)
  )
)

procedure(pgcEFindNet(mapping dbNet)
  let((found)
    found=nil
    ; Identity match, not name matching. Names never imply net equivalence.
    foreach(net mapping when(eq(net['db] dbNet) found=net))
    found
  )
)

procedure(pgcEConnection(ctx kind path ownerId instanceId port terminal netAnswer mapping reason)
  let((id netId status evidence netEntry)
    id=pgcENext(ctx "e") netId=nil status="unresolved" evidence="none"
    unless(reason
      cond(
        ((!terminal) reason="Selected CellView terminal is unavailable.")
        (terminal['unsupported] reason=terminal['unsupported])
        ((!netAnswer) reason="DB connectivity inspection failed or instTerm is absent.")
        ((!car(netAnswer)) status="unconnected" evidence="db")
        (t
          netEntry=pgcEFindNet(mapping car(netAnswer))
          cond(
            ((!netEntry) reason="DB net does not belong to the owning occurrence's local net collection.")
            (netEntry['unsupported] reason=netEntry['unsupported])
            (t netId=netEntry['id] status="connected" evidence="db")
          )
        )
      )
    )
    pgcEWrite(ctx 'connections pgcJObject(list(
      list("id" pgcJString(id)) list("path" pgcJString(path)) list("kind" pgcJString(kind))
      list("owner_instance_id" pgcJString(ownerId)) list("instance_id" pgcJString(instanceId))
      list("port" pgcJString(port)) list("terminal_id" pgcJNullableString(when(terminal terminal['id])))
      list("net_id" pgcJNullableString(netId)) list("status" pgcJString(status))
      list("evidence" pgcJString(evidence)) list("reason" pgcJNullableString(reason))
    )))
    when(reason pgcEIssue(ctx path "CONNECTION_UNRESOLVED" reason id))
  )
)

procedure(pgcECellPorts(ctx definition occurrenceId path mapping)
  foreach(term definition['terms]
    pgcEConnection(ctx "cell_port" pgcJPathAppend(pgcJPathAppend(path "cell_ports") term['name])
      occurrenceId occurrenceId term['name] term
      pgcEGet(ctx term['db] 'net path term['id]) mapping nil)
  )
)

; Parent instTerm connections are read independently from child cell_port nets.
; Every placed master terminal is emitted, plus selected-only mismatch ports.
procedure(pgcEInstancePorts(ctx inst master definition ownerId childId path mapping forcedReason)
  let((terms instTerms ports name selectedTerm matches termAnswer netAnswer reason dir answer)
    ports=nil
    terms=if(master then pgcEList(ctx master 'terminals path childId) else nil)
    instTerms=pgcEList(ctx inst 'instTerms path childId)
    foreach(term terms
      name=pgcERequiredString(ctx term 'name path childId)
      unless(member(name ports) ports=cons(name ports))
    )
    when(definition foreach(term definition['terms]
      unless(member(term['name] ports) ports=cons(term['name] ports))
    ))
    ; Retain observable instTerm names even when master inspection failed.
    foreach(instTerm instTerms
      name=pgcERequiredString(ctx instTerm 'name path childId)
      unless(member(name ports) ports=cons(name ports))
    )
    foreach(port reverse(ports)
      selectedTerm=pgcEFindTerm(definition port) matches=nil netAnswer=nil reason=forcedReason
      termAnswer=nil
      foreach(term terms
        answer=pgcEGet(ctx term 'name path childId)
        when(answer && equal(car(answer) port) termAnswer=term)
      )
      unless(reason
        cond(
          ((!selectedTerm) reason="Placed master port has no matching selected schematic terminal.")
          ((!termAnswer) reason="Selected schematic port has no matching placed master terminal.")
          (t
            dir=pgcEGet(ctx termAnswer 'direction path childId)
            unless(dir && equal(car(dir) selectedTerm['direction])
              reason="Placed master and selected schematic terminal directions differ or cannot be read.")
          )
        )
      )
      foreach(instTerm instTerms
        answer=pgcEGet(ctx instTerm 'name path childId)
        when(answer && equal(car(answer) port) matches=cons(instTerm matches))
      )
      unless(reason
        if(length(matches)==1 then
          ; Verify instTerm->term identity against the placed master.
          answer=pgcEGet(ctx car(matches) 'term path childId)
          if(answer && eq(car(answer) termAnswer) then
            netAnswer=pgcEGet(ctx car(matches) 'net path childId)
          else reason="instTerm does not reference the expected placed-master terminal.")
        else reason="Missing or duplicate instTerm; absence is not proof of an unconnected port.")
      )
      pgcEConnection(ctx "instance_port" pgcJPathAppend(pgcJPathAppend(path "instance_ports") port)
        ownerId childId port selectedTerm netAnswer mapping reason)
    )
  )
)

procedure(pgcEEmitInstance(ctx id path name parentId definition masterJson placement)
  pgcEWrite(ctx 'instances pgcJObject(list(
    list("id" pgcJString(id)) list("path" pgcJString(path)) list("name" pgcJString(name))
    list("parent_id" pgcJNullableString(parentId))
    list("cell_id" pgcJNullableString(when(definition definition['id])))
    list("master" masterJson) list("selected" if(definition then definition['view] else "null"))
    list("placement" placement)
  )))
)

procedure(pgcEWalk(ctx definition occurrenceId path ancestors depth)
  let((mapping childPath name libraryName cellName viewName childId masterAnswer master
       childDef masterJson reason seen arrayType numInst)
    mapping=pgcEOccurrenceNets(ctx definition occurrenceId path)
    pgcECellPorts(ctx definition occurrenceId path mapping)
    seen=nil
    foreach(inst definition['instances]
      name=pgcERequiredString(ctx inst 'name path occurrenceId)
      childPath=pgcJPathAppend(path name)
      libraryName=pgcERequiredString(ctx inst 'libName childPath occurrenceId)
      cellName=pgcERequiredString(ctx inst 'cellName childPath occurrenceId)
      viewName=pgcERequiredString(ctx inst 'viewName childPath occurrenceId)
      if(pgcEPinHelper(libraryName cellName viewName) then
        ctx['pin_helpers_skipped]=ctx['pin_helpers_skipped]+1
      else
        childId=pgcENext(ctx "i") reason=nil childDef=nil master=nil
        masterJson=pgcEView(libraryName cellName viewName)
        when(member(name seen)
          reason="Duplicate instance name in parent CellView."
          pgcEIssue(ctx childPath "DUPLICATE_INSTANCE_NAME" reason childId)
        )
        seen=cons(name seen)
        masterAnswer=pgcEGet(ctx inst 'master childPath childId)
        when(masterAnswer master=car(masterAnswer))
        unless(master
          reason="Placed master cannot be inspected."
          pgcEIssue(ctx childPath "MASTER_UNAVAILABLE" reason childId)
        )
        arrayType=pgcEGet(ctx inst 'objType childPath childId)
        when((arrayType && !equal(car(arrayType) "inst")) || pgcEUnsupportedName(name)
          reason="Instance arrays/buses/global occurrence spelling are unsupported."
          pgcEIssue(ctx childPath "INSTANCE_ARRAY_UNSUPPORTED" reason childId)
        )
        numInst=pgcEOptionalGet(ctx inst 'numInst childPath childId)
        when(!numInst || (car(numInst) && (!integerp(car(numInst)) || car(numInst)>1 || car(numInst)<1))
          reason="Array multiplicity is unsupported or could not be inspected."
          pgcEIssue(ctx childPath "INSTANCE_MULTIPLICITY_UNSUPPORTED" reason childId))
        when(pgcECheckExpressions(ctx inst childPath childId)
          reason="Inherited instance connections are unsupported.")
        when(equal(viewName "config")
          reason="Config/HDB elaboration is unsupported."
          pgcEIssue(ctx childPath "CONFIG_UNSUPPORTED" reason childId)
        )
        unless(reason
          childDef=pgcEDefinition(ctx libraryName cellName "schematic" childPath)
          unless(childDef reason="Explicit child schematic is unavailable.")
        )
        pgcEEmitInstance(ctx childId childPath name occurrenceId childDef masterJson
          pgcEPlacement(ctx inst childPath))
        unless(childDef pgcEIssue(ctx childPath "UNRESOLVED_INSTANCE"
          reason || "Analysis CellView could not be selected." childId))
        pgcEInstancePorts(ctx inst master childDef occurrenceId childId childPath mapping reason)
        when(childDef
          cond(
            (member(childDef['key] ancestors)
              pgcEIssue(ctx childPath "HIERARCHY_CYCLE" "Recursive hierarchy encountered; descent stopped." childId)
              ; Its own ports/nets remain observable, but no recursive descendants.
              pgcECellPorts(ctx childDef childId childPath pgcEOccurrenceNets(ctx childDef childId childPath)))
            ((depth>=ctx['max_depth])
              pgcEIssue(ctx childPath "MAX_DEPTH" "Hierarchy depth limit reached; descent stopped." childId)
              pgcECellPorts(ctx childDef childId childPath pgcEOccurrenceNets(ctx childDef childId childPath)))
            (t pgcEWalk(ctx childDef childId childPath cons(childDef['key] ancestors) depth+1))
          )
        )
      )
    )
  )
)

procedure(pgcECloseStreams(ctx)
  foreach(kind '(cells instances nets connections unresolved)
    when(ctx[kind]
      unless(drain(ctx[kind]) error("PGCHECK: output flush failed for %L; no final manifest\n" kind))
      unless(close(ctx[kind]) error("PGCHECK: output close failed for %L; no final manifest\n" kind))
      ctx[kind]=nil)
  )
  t
)

procedure(pgcECleanup(ctx)
  ; Close only references opened by this run. Do not dbPurge a user's CV.
  foreach(kind '(cells instances nets connections unresolved)
    when(ctx[kind] errset(close(ctx[kind]) t) ctx[kind]=nil)
  )
  foreach(cv ctx['opened] errset(dbClose(cv) t))
  ctx['opened]=nil
)

procedure(pgcEManifest(ctx libraryName cellName viewName)
  let((counts files capabilities status port pending final closeOK)
    counts=nil files=nil
    foreach(kind '(cells instances nets connections unresolved)
      counts=cons(list(symbolToString(kind) pgcJNumber(ctx['counts][kind])) counts)
      files=cons(list(symbolToString(kind) pgcJString(strcat(symbolToString(kind) ".jsonl"))) files)
    )
    status=if(ctx['counts]['unresolved]==0 then "complete" else "incomplete")
    capabilities=pgcJObject(list(
      list("binding_policy" pgcJString("explicit schematic; no Config/HDB elaboration"))
      list("source_access" pgcJString("read_only"))
      list("snapshot_source" pgcJString("source-session database; may include unsaved in-memory changes"))
      list("saved_status" pgcJString("NOT_TESTED")) list("connectivity_status" pgcJString("NOT_TESTED"))
      list("internal_acceptance" pgcJString("NOT_TESTED"))
      list("placement_support" pgcJString(if(ctx['placement_supported] then "partial_or_available" else "unavailable_or_no_children")))
      list("coordinate_units" pgcJString("unverified; placement units null"))
      list("utf8_locale" pgcJString(ctx['locale])) list("utf8_byte_validation" pgcJString("Python reader required"))
      list("global_net_resolution" pgcJString("unsupported; never merged"))
      list("inherited_resolution" pgcJString("unsupported; inherited term/signal APIs and netSet property types screened"))
      list("bus_array_expansion" pgcJString("unsupported; names and object types screened conservatively"))
      list("semantic_screening_limit" pgcJString("not a full elaboration; validate site-specific net semantics with probe/manual review"))
      list("pin_helper_policy" pgcJString("exclude only basic/{ipin,opin,iopin,sympin}/symbol"))
      list("pin_helpers_skipped" pgcJNumber(ctx['pin_helpers_skipped]))
      list("max_depth" pgcJNumber(ctx['max_depth]))
      list("warnings" pgcJArray(reverse(ctx['warnings])))
    ))
    ; Publish only a flushed/closed manifest. An interruption leaves the
    ; diagnostic manifest.pending file, never a falsely complete manifest.
    pending=strcat(ctx['output_dir] "/manifest.pending")
    final=strcat(ctx['output_dir] "/manifest.json")
    port=outfile(pending "w")
    unless(port error("PGCHECK: cannot create final manifest\n"))
    unwindProtect(
      progn(
        pgcJWriteLine(port pgcJObject(list(
          list("schema_version" pgcJString("1.0")) list("run_id" pgcJString(ctx['run_id]))
          list("status" pgcJString(status)) list("root_instance_id" pgcJString(ctx['root_id]))
          list("top" pgcEView(libraryName cellName viewName))
          list("files" pgcJObject(reverse(files))) list("counts" pgcJObject(reverse(counts)))
          list("capabilities" capabilities) list("validation_context" pgcJString("virtuoso_unverified"))
        )))
        unless(drain(port) error("PGCHECK: manifest flush failed; manifest.pending retained\n"))
        closeOK=close(port) port=nil
        unless(closeOK error("PGCHECK: manifest close failed; manifest.pending retained\n"))
        when(isFile(final) || isDir(final)
          error("PGCHECK: unexpected existing final manifest; refusing replacement\n"))
        unless(renameFile(pending final)
          error("PGCHECK: manifest publication failed; manifest.pending retained\n"))
      )
      when(port errset(close(port) t))
    )
    status
  )
)

procedure(pgcExport(libraryName cellName viewName outputDir @optional runId)
  let((ctx created definition path result status)
    foreach(value list(libraryName cellName viewName outputDir)
      unless(stringp(value) && strlen(value)>0 error("PGCHECK: nonempty string arguments required\n"))
    )
    unless(equal(viewName "schematic")
      error("PGCHECK Phase 0: top view must be explicitly schematic; Config/HDB is unsupported\n")
    )
    unless(substring(outputDir 1 1)=="/"
      error("PGCHECK: outputDir must be an absolute Linux path\n")
    )
    when(runId && (!stringp(runId) || strlen(runId)==0)
      error("PGCHECK: runId must be a nonempty string\n"))
    unless(isCallable('pgcJString) error("Load skill/pgcheck_json.il first\n"))
    foreach(api '(dbOpenCellViewByType dbGet dbFindProp dbClose createDir isDir isFile
                  outfile fprintf drain close renameFile)
      unless(isCallable(api) error("PGCHECK: required API unavailable: %L\n" api)))
    ctx=makeTable('pgcExportContext nil)
    ctx['locale]=pgcJRequireUtf8() pgcJsonSelfTest()
    ctx['serial]=0 ctx['counts]=makeTable('pgcCounts 0)
    ctx['definitions]=makeTable('pgcDefinitions nil)
    ctx['opened]=nil ctx['warnings]=nil ctx['placement_supported]=nil
    ctx['pin_helpers_skipped]=0 ctx['max_depth]=64 ctx['output_dir]=outputDir
    ctx['run_id]=if(runId then runId else outputDir)
    ctx['root_id]=pgcENext(ctx "i")
    ; createDir must itself succeed, so a race creating the directory is a
    ; refusal, not permission to truncate files. Parent must already exist.
    when(isDir(outputDir) || isFile(outputDir)
      error("PGCHECK: output path already exists; refusing overwrite: %s\n" outputDir))
    created=errset(createDir(outputDir) t)
    unless(created && car(created) error("PGCHECK: new output directory creation failed\n"))
    unwindProtect(
      progn(
        foreach(kind '(cells instances nets connections unresolved)
          ctx[kind]=outfile(strcat(outputDir "/" symbolToString(kind) ".jsonl") "w")
          unless(ctx[kind] error("PGCHECK: failed to open output stream %L; keep partial directory\n" kind))
        )
        path=pgcEKey(libraryName cellName viewName)
        result=errset(
          progn(
            definition=pgcEDefinition(ctx libraryName cellName viewName path)
            pgcEEmitInstance(ctx ctx['root_id] path cellName nil definition
              pgcEView(libraryName cellName viewName) "null")
            unless(definition pgcEIssue(ctx path "UNRESOLVED_ROOT"
              "Top schematic could not be opened for analysis." ctx['root_id]))
            when(definition pgcEWalk(ctx definition ctx['root_id] path list(definition['key]) 0))
          ) t)
        unless(result
          pgcEIssue(ctx path "EXPORT_INTERRUPTED"
            "Unexpected SKILL extraction error; inspect local CIW/log. Output is incomplete and may fail validation."
            nil)
        )
        ; A close/write failure aborts finalization, leaving no valid manifest.
        pgcECloseStreams(ctx)
        status=pgcEManifest(ctx libraryName cellName viewName)
        printf("PGCHECK export %s: %s (internal acceptance NOT_TESTED).\n" outputDir status)
        status
      )
      pgcECleanup(ctx)
    )
  )
)
