; Minimal Motorola DSP56001 I/O equates used by the WC1 C2P worker.

m_bcr   EQU     $FFFE           ; Port A Bus Control Register
m_pbc   EQU     $FFE0           ; Port B Control Register

m_hcr   EQU     $FFE8           ; Host Control Register
m_hsr   EQU     $FFE9           ; Host Status Register
m_hrx   EQU     $FFEB           ; Host Receive Data Register
m_htx   EQU     $FFEB           ; Host Transmit Data Register

m_hf2   EQU     3               ; host flag 2
m_hrdf  EQU     0               ; host receive data full
m_htde  EQU     1               ; host transmit data empty
