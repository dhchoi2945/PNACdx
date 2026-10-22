; PGCHECK Phase 0 T01 generator. IC25 runtime validation: NOT_TESTED externally.
; Default is DRY-RUN. Only create=t enables writes to the specified EXISTING lib.
; No library creation, overwrite mode, deletion, or rollback deletion is used.
; The owner must reserve PGC_T01_TOP and PGC_T01_LOAD against concurrent writers.

procedure(pgctLog(port status text)
  fprintf(port "%s %s\n" status text)
  drain(port)
)

procedure(pgctNeed(value context)
  unless(value error("PGCHECK T01: %s\n" context))
  value
)

procedure(pgctPreflight(lib port)
  let((clear)
    pgctNeed(and(stringp(lib) strlen(lib)>0) "An explicit allowed library name is required")
    pgctNeed(ddGetObj(lib) "Requested library does not exist; no library will be created")
    clear=t
    ; Inspect BOTH cells and ALL three target views before any write.
    ; A cell collision is fatal even if only an unrelated view exists.
    foreach(cell '("PGC_T01_TOP" "PGC_T01_LOAD")
      if(ddGetObj(lib cell) then
        clear=nil
        pgctLog(port "FAIL" sprintf(nil "Existing cell collision: %s/%s" lib cell))
      else
        pgctLog(port "NOT_TESTED" sprintf(nil "Target cell absent: %s/%s" lib cell))
      )
    )
    foreach(target '(("PGC_T01_TOP" "schematic")
                     ("PGC_T01_LOAD" "schematic")
                     ("PGC_T01_LOAD" "symbol"))
      when(ddGetObj(lib car(target) cadr(target))
        clear=nil
        pgctLog(port "FAIL"
          sprintf(nil "Existing view collision: %s/%s/%s" lib car(target) cadr(target)))
      )
    )
    pgctNeed(clear "Preflight conflict; no target was opened for editing")
    t
  )
)

procedure(pgctApiPreflight(port)
  let((ready)
    ready=t
    foreach(fn '(ddGetObj dbOpenCellViewByType dbClose dbCreateNet dbCreateTerm
                 dbCreatePin dbCreateRect dbCreateLine dbCreateLabel dbCreateInst
                 dbCreateInstTerm dbFindNetByName dbFindTermByName dbSave
                 schCreatePin schCreateWire schCreateWireLabel schCheck dbIsConnCurrent)
      unless(isCallable(fn)
        ready=nil
        pgctLog(port "BLOCKED" sprintf(nil "Required API not callable: %s" symbolToString(fn)))
      )
    )
    pgctNeed(ready "Required API missing; inspect local documentation/probe and use manual fallback")
    t
  )
)

procedure(pgctOpenNew(lib cell view viewType port)
  let((cv)
    ; Immediate check reduces the race window; append mode never truncates a view.
    pgctNeed(null(ddGetObj(lib cell view)) "Target appeared after preflight; stop immediately")
    pgctLog(port "NOT_TESTED" sprintf(nil "NEW_OPEN_ATTEMPT %s/%s/%s; inspect this target on any failure" lib cell view))
    cv=pgctNeed(dbOpenCellViewByType(lib cell view viewType "a")
      sprintf(nil "Cannot create %s/%s/%s in append mode" lib cell view))
    ; If an existing view won a race and has content, do NOT add anything to it.
    pgctNeed(and(null(cv~>instances) null(cv~>shapes) null(cv~>nets) null(cv~>terminals))
      "Newly opened target is nonempty; possible concurrent creator; do not modify")
    pgctLog(port "NOT_TESTED" sprintf(nil "NEW_OPEN %s/%s/%s; partial state may now exist" lib cell view))
    cv
  )
)

procedure(pgctNet(cv name)
  pgctNeed(dbCreateNet(cv name) sprintf(nil "Cannot create local net %s" name))
)

procedure(pgctLabel(cv wire point name)
  pgctNeed(schCreateWireLabel(cv car(wire) point name "lowerLeft" "R0" "stick" 0.125 nil)
    sprintf(nil "Cannot create electrical wire label %s" name))
)

procedure(pgctWire(cv start finish name)
  let((wire)
    wire=pgctNeed(schCreateWire(cv "route" "full" list(start finish) 0.0625 0.0625 0.0)
      sprintf(nil "Cannot create schematic wire for %s" name))
    pgctLabel(cv wire start name)
    wire
  )
)

procedure(pgctPin(cv master name direction point)
  pgctNeed(schCreatePin(cv master name direction nil point "R0")
    sprintf(nil "Cannot create schematic pin %s" name))
  ; Wire labels and schematic extraction establish the visible connectivity.
  pgctWire(cv point list(car(point)+3.0 cadr(point)) name)
)

procedure(pgctCheckSave(cv port)
  let((checkResult)
    checkResult=schCheck(cv)
    pgctLog(port "NOT_TESTED" sprintf(nil "schCheck %s returned %L" cv~>cellName checkResult))
    pgctNeed(dbIsConnCurrent(cv) "Connectivity is not current after schCheck")
    pgctNeed(dbSave(cv) "dbSave failed; a partial DB may remain")
    ; A nil saved flag alone is not treated as proof of checker correctness.
    pgctLog(port "NOT_TESTED" sprintf(nil "Saved new %s/%s/%s; modifiedButNotSaved=%L"
      cv~>libName cv~>cellName cv~>viewName cv~>modifiedButNotSaved))
    t
  )
)

procedure(pgctSymbolPin(cv name direction y)
  let((net term fig)
    net=pgctNet(cv name)
    term=pgctNeed(dbCreateTerm(net name direction) "Cannot create symbol terminal")
    fig=pgctNeed(dbCreateRect(cv '("pin" "drawing")
      list(list(-0.0625 y-0.0625) list(0.0625 y+0.0625))) "Cannot create symbol pin rectangle")
    pgctNeed(dbCreatePin(net fig name) "Cannot associate symbol pin with its net")
    pgctNeed(dbCreateLine(cv '("device" "drawing") list(list(0.0 y) list(0.5 y)))
      "Cannot create visible symbol pin lead")
    pgctNeed(dbCreateLabel(cv '("pin" "drawing") list(0.625 y) name
      "centerLeft" "R0" "stick" 0.125) "Cannot create visible symbol pin name")
    term
  )
)

procedure(pgctBuildSymbol(cv)
  pgctNeed(dbCreateRect(cv '("device" "drawing") list(0.5:-2.5 3.0:2.5)) "Cannot draw LOAD body")
  pgctNeed(dbCreateRect(cv '("instance" "drawing") list(0.0:-2.5 3.0:2.5)) "Cannot draw selection box")
  pgctNeed(dbCreateLabel(cv '("device" "drawing") 1.75:1.0 "PGC_T01_LOAD"
    "centerCenter" "R0" "stick" 0.125) "Cannot label LOAD symbol")
  pgctSymbolPin(cv "VDD" "inputOutput" 2.0)
  pgctSymbolPin(cv "VSS" "inputOutput" 0.0)
  pgctSymbolPin(cv "EN" "input" -2.0)
  pgctNeed(dbSave(cv) "Cannot save new LOAD symbol")
  t
)

procedure(pgctBuildLoad(cv iopin ipin)
  pgctPin(cv iopin "VDD" "inputOutput" 0.0:2.0)
  pgctPin(cv iopin "VSS" "inputOutput" 0.0:0.0)
  pgctPin(cv ipin "EN" "input" 0.0:-2.0)
  t
)

procedure(pgctConnect(cv inst master portName netName point)
  let((net term)
    net=pgctNeed(dbFindNetByName(cv netName) "Missing parent net before instTerm creation")
    term=pgctNeed(dbFindTermByName(master portName) "Missing placed symbol terminal")
    pgctNeed(dbCreateInstTerm(net inst term) "Cannot create actual DB instance-port connection")
    pgctWire(cv list(car(point)-3.0 cadr(point)) point netName)
    t
  )
)

procedure(pgctBuildTop(cv symbol iopin ipin)
  let((u0 u1)
    pgctPin(cv iopin "VDD_A" "inputOutput" 0.0:10.0)
    pgctPin(cv iopin "VDD_B" "inputOutput" 0.0:0.0)
    pgctPin(cv iopin "VSS_A" "inputOutput" 0.0:8.0)
    pgctPin(cv ipin "CTRL" "input" 0.0:6.0)
    u0=pgctNeed(dbCreateInst(cv symbol "U_LOAD0" 8.0:8.0 "R0" 1) "Cannot place U_LOAD0")
    u1=pgctNeed(dbCreateInst(cv symbol "U_LOAD1" 8.0:-2.0 "R0" 1) "Cannot place U_LOAD1")
    pgctConnect(cv u0 symbol "VDD" "VDD_A" 8.0:10.0)
    pgctConnect(cv u0 symbol "VSS" "VSS_A" 8.0:8.0)
    pgctConnect(cv u0 symbol "EN" "CTRL" 8.0:6.0)
    pgctConnect(cv u1 symbol "VDD" "VDD_B" 8.0:0.0)
    pgctConnect(cv u1 symbol "VSS" "VSS_A" 8.0:-2.0)
    pgctConnect(cv u1 symbol "EN" "CTRL" 8.0:-4.0)
    t
  )
)

procedure(pgctVerifyPorts(cv expected)
  let((term net)
    pgctNeed(length(cv~>terminals)==length(expected) "Unexpected terminal count")
    pgctNeed(length(cv~>nets)==length(expected) "Unexpected local net count")
    foreach(pair expected
      term=pgctNeed(dbFindTermByName(cv car(pair)) "Expected terminal absent")
      net=pgctNeed(dbFindNetByName(cv car(pair)) "Expected local net absent")
      pgctNeed(equal(term~>direction cadr(pair)) "Terminal direction mismatch")
      pgctNeed(eq(term~>net net) "Cell port is not connected to its expected local DB net")
      pgctNeed(term~>pins "Terminal lacks an actual visible pin")
    )
    t
  )
)

procedure(pgctVerifyTop(top symbol)
  let((inst found instTerm circuitCount)
    circuitCount=0
    foreach(candidate top~>instances
      when(equal(candidate~>cellName "PGC_T01_LOAD") circuitCount=circuitCount+1)
    )
    pgctNeed(circuitCount==2 "TOP must have exactly two LOAD instances")
    foreach(row '(("U_LOAD0" "VDD" "VDD_A") ("U_LOAD0" "VSS" "VSS_A")
                  ("U_LOAD0" "EN" "CTRL") ("U_LOAD1" "VDD" "VDD_B")
                  ("U_LOAD1" "VSS" "VSS_A") ("U_LOAD1" "EN" "CTRL"))
      found=setof(candidate top~>instances equal(candidate~>name car(row)))
      pgctNeed(length(found)==1 "Missing or duplicated LOAD occurrence")
      inst=car(found)
      pgctNeed(eq(inst~>master symbol) "Placed master is not newly created LOAD/symbol")
      found=setof(it inst~>instTerms equal(it~>name cadr(row)))
      pgctNeed(length(found)==1 "Missing or duplicated instTerm after schCheck")
      instTerm=car(found)
      pgctNeed(eq(instTerm~>net dbFindNetByName(top caddr(row)))
        sprintf(nil "Wrong actual connectivity %s.%s -> expected %s" car(row) cadr(row) caddr(row)))
    )
    t
  )
)

procedure(pgctReadback(lib port)
  let((symbol load top attempt)
    attempt=errset(
      progn(
        symbol=pgctNeed(dbOpenCellViewByType(lib "PGC_T01_LOAD" "symbol" "" "r")
          "Saved symbol cannot be reopened read-only")
        load=pgctNeed(dbOpenCellViewByType(lib "PGC_T01_LOAD" "schematic" "" "r")
          "Saved LOAD schematic cannot be reopened read-only")
        top=pgctNeed(dbOpenCellViewByType(lib "PGC_T01_TOP" "schematic" "" "r")
          "Saved TOP schematic cannot be reopened read-only")
        pgctNeed(dbIsConnCurrent(load) "Reopened LOAD connectivity is not current")
        pgctNeed(dbIsConnCurrent(top) "Reopened TOP connectivity is not current")
        pgctVerifyPorts(symbol '(("VDD" "inputOutput") ("VSS" "inputOutput") ("EN" "input")))
        pgctVerifyPorts(load '(("VDD" "inputOutput") ("VSS" "inputOutput") ("EN" "input")))
        pgctVerifyPorts(top '(("VDD_A" "inputOutput") ("VDD_B" "inputOutput")
                              ("VSS_A" "inputOutput") ("CTRL" "input")))
        pgctVerifyTop(top symbol)
        pgctLog(port "NOT_TESTED" "READBACK_OK: saved views reopened with access=r; expected connectivity rechecked")
        t
      ) t)
    when(top errset(dbClose(top) t))
    when(load errset(dbClose(load) t))
    when(symbol errset(dbClose(symbol) t))
    and(attempt car(attempt))
  )
)

procedure(pgctGenerateBody(lib create port)
  let((iopin ipin load symbol top attempt created)
    pgctPreflight(lib port)
    if(not(eq(create t)) then
      pgctLog(port "NOT_TESTED" "DRY_RUN: 3 target views absent; no database write requested")
      pgctLog(port "NOT_TESTED" "Use pgcGenerateT01(lib t logFile) only after reserving both test cell names")
      t
    else
      pgctApiPreflight(port)
      ; Pin helper masters are read-only, in basic; no other library is written.
      iopin=pgctNeed(dbOpenCellViewByType("basic" "iopin" "symbol" "" "r") "basic/iopin/symbol unavailable")
      ipin=pgctNeed(dbOpenCellViewByType("basic" "ipin" "symbol" "" "r") "basic/ipin/symbol unavailable")
      ; Recheck every target after helper/API preflight and before first DB write.
      pgctPreflight(lib port)
      pgctLog(port "NOT_TESTED" "CREATE_BEGIN: append mode; exclusive ownership is required to avoid check/open race")
      attempt=errset(
        progn(
          pgctNeed(null(ddGetObj(lib "PGC_T01_LOAD")) "LOAD cell appeared after preflight")
          symbol=pgctOpenNew(lib "PGC_T01_LOAD" "symbol" "schematicSymbol" port)
          created=cons("PGC_T01_LOAD/symbol" created)
          pgctBuildSymbol(symbol)
          load=pgctOpenNew(lib "PGC_T01_LOAD" "schematic" "schematic" port)
          created=cons("PGC_T01_LOAD/schematic" created)
          pgctBuildLoad(load iopin ipin)
          pgctCheckSave(load port)
          ; TOP cell must still be absent, even if a concurrent unrelated view appeared.
          pgctNeed(null(ddGetObj(lib "PGC_T01_TOP")) "TOP cell appeared after preflight")
          top=pgctOpenNew(lib "PGC_T01_TOP" "schematic" "schematic" port)
          created=cons("PGC_T01_TOP/schematic" created)
          pgctBuildTop(top symbol iopin ipin)
          pgctCheckSave(top port)
          pgctVerifyPorts(symbol '(("VDD" "inputOutput") ("VSS" "inputOutput") ("EN" "input")))
          pgctVerifyPorts(load '(("VDD" "inputOutput") ("VSS" "inputOutput") ("EN" "input")))
          pgctVerifyPorts(top '(("VDD_A" "inputOutput") ("VDD_B" "inputOutput")
                                ("VSS_A" "inputOutput") ("CTRL" "input")))
          pgctVerifyTop(top symbol)
          dbClose(top)
          top=nil
          dbClose(load)
          load=nil
          dbClose(symbol)
          symbol=nil
          pgctNeed(pgctReadback(lib port) "Read-only saved-view readback failed; inspect partial state")
          pgctLog(port "PASS" "Generator local checks: 3 views saved/reopened; DB terminal/instTerm/net identities match independent T01 table")
          pgctLog(port "NOT_TESTED" "CIW visual inspection, exporter/validator and user acceptance are separate mandatory checks")
          t
        ) t)
      if(attempt then
        ; Only close successfully saved new views; never check/save original designs.
        when(top errset(dbClose(top) t))
        when(load errset(dbClose(load) t))
        when(symbol errset(dbClose(symbol) t))
      else
        pgctLog(port "FAIL" sprintf(nil "PARTIAL_CREATION possible; opened targets=%L; inspect CIW error above" reverse(created)))
        pgctLog(port "FAIL" "No rollback or deletion performed. New writable handles are left in-session for diagnosis; do not rerun over them")
      )
      when(ipin errset(dbClose(ipin) t))
      when(iopin errset(dbClose(iopin) t))
      and(attempt car(attempt))
    )
  )
)

procedure(pgcGenerateT01(lib @optional (create nil) (logFile "pgcheck-t01.local.log"))
  let((port attempt)
    unless(or(null(create) eq(create t))
      error("PGCHECK T01: create must be nil (dry-run) or explicit t (create).\n"))
    port=outfile(logFile "a")
    unless(port error("PGCHECK T01: cannot append approved local log %L\n" logFile))
    pgctLog(port "NOT_TESTED" sprintf(nil "PGCHECK T01 begin library=%L create=%L" lib create))
    attempt=errset(pgctGenerateBody(lib create port) t)
    unless(attempt
      pgctLog(port "FAIL" "Stopped by preflight/runtime error; detailed error remains in local CIW log")
    )
    close(port)
    and(attempt car(attempt))
  )
)
