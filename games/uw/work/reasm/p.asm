bits 16
org 0
 es lodsw
 rep es movsb
 es rep movsb
 cs lodsb
 repne scasw
 lock inc word [bx]
