; PGCHECK Phase 0 - read-only API/environment probe.
; IC25.1-64b.SM_ISR7.10 runtime validation: NOT_TESTED by external development.
; No dbSave/schCheck, library creation, HDB mutation, or shell execution occurs.
; Report files are local plain text, append-only; keep them inside the company.

procedure(pgcpPresence(port names)
  foreach(fn names
    fprintf(port "PRESENCE %s callable=%L semantic_status=NOT_TESTED\n"
      symbolToString(fn) isCallable(fn))
  )
)

procedure(pgcpRead(port label obj attr)
  let((attempt)
    if(isCallable('dbGet) then
      attempt=errset(dbGet(obj attr) t)
      if(attempt then
        fprintf(port "READ_OK %s.%s value=%L (nil is not proof of attribute support)\n"
          label symbolToString(attr) car(attempt))
      else
        fprintf(port "READ_ERROR %s.%s status=BLOCKED; see local CIW diagnostics\n"
          label symbolToString(attr))
      )
    else
      fprintf(port "READ_SKIPPED %s.%s dbGet unavailable status=BLOCKED\n"
        label symbolToString(attr))
    )
  )
)

procedure(pgcpInspect(port label obj attrs)
  when(obj
    foreach(attr attrs pgcpRead(port label obj attr))
  )
)

procedure(pgcpInspectCv(port cv)
  let((attempt inst term net sig header prop)
    pgcpInspect(port "cellview" cv
      '(libName cellName viewName cellViewType mode modifiedButNotSaved
        DBUPerUU userUnits terminals nets signals instances mosaics instHeaders prop))
    when(isCallable('dbIsConnCurrent)
      attempt=errset(dbIsConnCurrent(cv) t)
      fprintf(port "dbIsConnCurrent guarded_result=%L\n" attempt)
    )
    when(isCallable('dbGetCellViewInheritedTerm)
      attempt=errset(dbGetCellViewInheritedTerm(cv) t)
      fprintf(port "dbGetCellViewInheritedTerm guarded_result=%L\n" attempt)
    )
    when(isCallable('dbGetCellViewInheritedSig)
      attempt=errset(dbGetCellViewInheritedSig(cv) t)
      fprintf(port "dbGetCellViewInheritedSig guarded_result=%L\n" attempt)
    )
    when(isCallable('dbCVHasNetSetProp)
      attempt=errset(dbCVHasNetSetProp(cv) t)
      fprintf(port "dbCVHasNetSetProp guarded_result=%L\n" attempt)
    )
    attempt=errset(car(cv~>instances) t)
    when(attempt
      inst=car(attempt)
      pgcpInspect(port "sample_instance" inst
        '(name objType master instTerms xy orient transform numInst mosaic prop))
      when(inst
        attempt=errset(car(inst~>prop) t)
        when(attempt
          prop=car(attempt)
          pgcpInspect(port "sample_instance_property" prop '(name valueType value))
        )
      )
    )
    attempt=errset(car(cv~>terminals) t)
    when(attempt
      term=car(attempt)
      pgcpInspect(port "sample_terminal" term '(name direction net pins))
      when(and(term isCallable('dbGetTermNetExpr))
        attempt=errset(dbGetTermNetExpr(term) t)
        fprintf(port "dbGetTermNetExpr guarded_result=%L\n" attempt)
      )
    )
    attempt=errset(car(cv~>nets) t)
    when(attempt
      net=car(attempt)
      pgcpInspect(port "sample_net" net '(name signals numBits sigNames term instTerms))
      when(net
        attempt=errset(car(net~>signals) t)
        when(attempt
          sig=car(attempt)
          pgcpInspect(port "sample_signal" sig '(name isGlobal sigType memInstTerms memNets))
          when(and(sig isCallable('dbGetSigNetExpr))
            attempt=errset(dbGetSigNetExpr(sig) t)
            fprintf(port "dbGetSigNetExpr guarded_result=%L\n" attempt)
          )
        )
      )
    )
    attempt=errset(car(cv~>instHeaders) t)
    when(attempt
      header=car(attempt)
      pgcpInspect(port "sample_instHeader" header '(masterChangeCount master instances))
      when(header
        attempt=errset(header~>master~>modifiedCounter t)
        fprintf(port "sample_instHeader.master.modifiedCounter guarded_result=%L\n" attempt)
      )
    )
    t
  )
)

procedure(pgcProbe(outputFile @optional lib cell (view "schematic"))
  let((port attempt cv closeAttempt reportOk)
    unless(and(stringp(outputFile) strlen(outputFile)>0)
      error("PGCHECK probe: outputFile must be an approved local filename.\n"))
    port=outfile(outputFile "a")
    unless(port error("PGCHECK probe: cannot append local report %L\n" outputFile))
    fprintf(port "\nPGCHECK Phase 0 API Probe\n")
    fprintf(port "external_runtime_validation=NOT_TESTED\n")
    fprintf(port "A callable symbol is a candidate, not proof of signature or IC25 support.\n")
    fprintf(port "READ_OK means only that one guarded read did not throw; nil may mean unavailable.\n")
    fprintf(port "No original DB is checked, saved, repaired or deliberately modified.\n")
    attempt=errset(getVersion(t) t)
    fprintf(port "getVersion guarded_result=%L\n" attempt)
    pgcpPresence(port
      '(ddGetObj dbOpenCellViewByType dbClose dbGet dbFindProp dbFindNetByName
        dbFindTermByName dbFindAnyInstByName dbCreateNet dbCreateTerm dbCreatePin
        dbCreateInst dbCreateInstTerm dbCreateRect dbCreateLine dbCreateLabel
        dbSave schCreatePin schCreateWire schCreateWireLabel schCheck dbIsConnCurrent
        dbGetCellViewInheritedTerm dbGetCellViewInheritedSig dbGetTermNetExpr
        dbGetSigNetExpr dbParseTermNetExpr dbCVHasNetSetProp dbGetAnyInstSwitchMaster
        hdbOpen hdbClose hdbGetTopLibName hdbGetTopCellName hdbGetTopViewName
        hdbGetInstHeaderMaster hdbExplainBinding createDir isDir isFile
        sprintf substring strlen getAscii charToInt))
    reportOk=t
    if(and(lib cell) then
      fprintf(port "requested_cellview=%L/%L/%L access=r\n" lib cell view)
      attempt=errset(dbOpenCellViewByType(lib cell view "" "r") t)
      if(and(attempt car(attempt)) then
        cv=car(attempt)
        attempt=errset(pgcpInspectCv(port cv) t)
        unless(attempt
          reportOk=nil
          fprintf(port "INSPECTION_ABORTED status=BLOCKED; see local CIW diagnostics\n")
        )
        closeAttempt=errset(dbClose(cv) t)
        fprintf(port "read_handle_close=%L\n" closeAttempt)
      else
        reportOk=nil
        fprintf(port "OPEN_FAILED status=BLOCKED; no DB write attempted\n")
      )
    else
      fprintf(port "No lib/cell supplied: DB inspection NOT_TESTED (presence-only report).\n")
    )
    fprintf(port "Config binding / global inheritance / bus expansion semantics=NOT_TESTED\n")
    fprintf(port "Probe report generation finished; this is not Phase 0 acceptance.\n")
    close(port)
    reportOk
  )
)
