; PGCHECK Phase 0: small strict JSON encoder. ASCII source, UTF-8 output.
; Load this file before pgcheck_export.il. No database writes or shell calls.
; Runtime acceptance on IC25.1 is NOT_TESTED; run pgcProbe in the internal site.

procedure(pgcJString(value)
  let((answer ch controlIndex controls i)
    unless(stringp(value) error("PGCHECK JSON: expected string, got %L\n" value))
    ; A SKILL string is traversed without interpreting its non-ASCII bytes.
    ; Locale must be UTF-8; pgcJRequireUtf8 checks that before an export.
    controls="\001\002\003\004\005\006\007\010\011\012\013\014\015\016\017\020\021\022\023\024\025\026\027\030\031\032\033\034\035\036\037"
    answer="\""
    for(i 1 strlen(value)
      ch=substring(value i 1)
      controlIndex=nindex(controls ch)
      cond(
        (equal(ch "\"") answer=strcat(answer "\\\""))
        (equal(ch "\\") answer=strcat(answer "\\\\"))
        (equal(ch "\000") answer=strcat(answer "\\u0000"))
        (controlIndex answer=strcat(answer sprintf(nil "\\u%04x" controlIndex)))
        (t answer=strcat(answer ch))
      )
    )
    strcat(answer "\"")
  )
)

procedure(pgcJNullableString(value)
  if(value then pgcJString(value) else "null")
)

procedure(pgcJNumber(value)
  let((textValue answer ch i)
    unless(numberp(value) error("PGCHECK JSON: expected number\n"))
    ; NaN, infinity, and extremely large values are refused conservatively.
    unless(value==value && abs(value)<1.0e300
      error("PGCHECK JSON: non-finite/out-of-range numeric value\n")
    )
    textValue=if(integerp(value) then sprintf(nil "%d" value)
                else sprintf(nil "%.17g" value))
    ; printf's decimal separator can depend on LC_NUMERIC. There is no
    ; grouping flag here, so a comma, if present, is the decimal separator.
    answer=""
    for(i 1 strlen(textValue)
      ch=substring(textValue i 1)
      answer=strcat(answer if(equal(ch ",") then "." else ch))
    )
    answer
  )
)

procedure(pgcJArray(encodedValues)
  let((answer separator)
    answer="[" separator=""
    foreach(value encodedValues
      unless(stringp(value) error("PGCHECK JSON: array item is not encoded JSON\n"))
      answer=strcat(answer separator value) separator=","
    )
    strcat(answer "]")
  )
)

procedure(pgcJObject(pairs)
  let((answer separator keys key)
    answer="{" separator="" keys=nil
    foreach(pair pairs
      key=car(pair)
      when(member(key keys) error("PGCHECK JSON: duplicate key %s\n" key))
      keys=cons(key keys)
      unless(stringp(cadr(pair)) error("PGCHECK JSON: object value is not encoded JSON\n"))
      answer=strcat(answer separator pgcJString(key) ":" cadr(pair))
      separator=","
    )
    strcat(answer "}")
  )
)

procedure(pgcJPathAppend(path component)
  let((answer ch i)
    unless(stringp(path) && stringp(component)
      error("PGCHECK path: string arguments required\n")
    )
    answer=strcat(path "/")
    for(i 1 strlen(component)
      ch=substring(component i 1)
      answer=strcat(answer cond((equal(ch "~") "~0")
                               (equal(ch "/") "~1") (t ch)))
    )
    answer
  )
)

procedure(pgcJRequireUtf8()
  let((localeValue)
    unless(isCallable('getShellEnvVar)
      error("PGCHECK: getShellEnvVar unavailable; encoding preflight BLOCKED\n")
    )
    localeValue=getShellEnvVar("LC_ALL")
    unless(localeValue && strlen(localeValue)>0
      localeValue=getShellEnvVar("LC_CTYPE")
    )
    unless(localeValue && strlen(localeValue)>0
      localeValue=getShellEnvVar("LANG")
    )
    unless(localeValue &&
      (index(upperCase(localeValue) "UTF-8") || index(upperCase(localeValue) "UTF8"))
      error("PGCHECK: UTF-8 locale required before launching Virtuoso (LC_ALL/LC_CTYPE/LANG).\n")
    )
    localeValue
  )
)

procedure(pgcJWriteLine(port encodedObject)
  unless(port error("PGCHECK: output port is not open\n"))
  unless(fprintf(port "%s\n" encodedObject)
    error("PGCHECK: formatted output failed\n"))
  t
)

; Deterministic encoder checks runnable in CIW without any design database.
; This does not establish that the operating system wrote valid UTF-8 bytes.
procedure(pgcJsonSelfTest()
  unless(equal(pgcJString("a\"b\\c\nd\te\r") "\"a\\\"b\\\\c\\u000ad\\u0009e\\u000d\"")
    error("PGCHECK: JSON escape self-test failed\n")
  )
  unless(equal(pgcJPathAppend("/a" "~/b") "/a/~0~1b")
    error("PGCHECK: structural path self-test failed\n")
  )
  unless(equal(pgcJObject(list(list("x" pgcJNumber(12)))) "{\"x\":12}")
    error("PGCHECK: JSON object self-test failed\n")
  )
  t
)
