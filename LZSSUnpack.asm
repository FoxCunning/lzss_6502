; MIT Licence
;
; Copyright (c) 2021 Fox Cunning
;
; Permission is hereby granted, free of charge, to any person obtaining a copy
; of this software and associated documentation files (the "Software"), to deal
; in the Software without restriction, including without limitation the rights
; to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
; copies of the Software, and to permit persons to whom the Software is
; furnished to do so, subject to the following conditions:
;
; The above copyright notice and this permission notice shall be included in
; all copies or substantial portions of the Software.
;
; THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
; IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
; FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
; AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
; LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
; OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
; SOFTWARE.

; Example command line to compile with 64TASS:
; 64tass -X -f -b -o LZSSUnpack.bin -L LZSSUnpack.lst -Wno-pc-wrap LZSSUnpack.asm

.cpu "6502i"

; Parameters (adjust zero page addresses to your needs):

; $41, $42 = source address
*=	$41
src_lo		.byte ?
src_hi		.byte ?

; $29, $2A = destination address
*=	$29
dst_lo		.byte ?
dst_hi		.byte ?


; Variables used (adjust zero page addresses to your needs):

; $4F = temp data/flag/count holder
*=	$4F
tmp			.byte ?

; $2B, $2C = temp address used for back references
*=	$2B
backptr_lo	.byte ?
backptr_hi	.byte ?

; $B4 = flags
*=	$B4
flags		.byte ?

; $B5 = flags consumed
*=	$B5
consumed	.byte ?


; Constants:

; End address (adjust this to your needs)
end_lo =	#$00
end_hi =	#$80

; Since we don't work on files, we can't end the routine when EOF is reached,
; so we must know either the compressed or uncompressed size.
; The latter is more common, e.g. a full NES nametable is always 1KB,
; a full charset is 4KB, etc.
; See comments below to use a known compressed size instead.

; -----------------------------------------------------------------------------

LZSSUnpack:
	lda #$00
	sta flags ; Zero flags
	lda #$07
	sta consumed
dounpack:
	lsr flags
	lda dst_hi
	
	; Check whether we have reached the end of the uncompressed data
	; This is if we work with a known, constant uncompressed size
	cmp end_hi
	bne _start
	; No need to check low byte if it's 1KB aligned (e.g. $8000, $7200...)
	; lda dst_lo
	; cmp end_lo
	; bne _start 
	rts

_start:
	; Increment flags consumed count and check if we have consumed all of them
	lda #$09
	isc consumed
	bne _nonewflags

	ldx #$00
	lda (src_lo,X)
	sta tmp

	inc src_lo
	bne _nocarry0
	inc src_hi
_nocarry0:

	; If the uncompressed size is not known, but the compressed size is, then
	; we can check it here using end_lo, end_hi as variables in zero page
	; lda src_lo
	; cmp end_lo
	; bne _continue
	; lda src_hi
	; cmp end_hi
	; bne _continue
	; rts
	; _continue:

	; Load flags
	lda tmp	; We will use this to hold read bytes
	sta flags
	; Reset consumed flags count
	lda #$00
	sta consumed
	
_nonewflags:
	; Get flags and check if bit 0 is set
	lda flags
	lsr
	bcc _unpackdata

	; If not, copy next byte as is
	ldx #$00
	lda (src_lo,X)
	sta tmp
	
	; Advance source pointer
	inc src_lo
	bne _noCarry1
	inc src_hi
_noCarry1:

	lda tmp
	ldx #$00
	sta (dst_lo,X)

	; Advance destination pointer
	inc dst_lo
	bne dounpack
	inc dst_hi
_noCarry2:
	
	jmp dounpack
	
_unpackdata:
	; Read offset
	ldx #$00
	lda (src_lo,X)
	; Offset in Y (negated: we  move backwards)
	eor #$FF
	tay
	
	inc src_lo
	bne _noCarry3
	inc src_hi
_noCarry3:
	
	; Get count
	ldx #$00
	lda (src_lo,X)
	tax

	inc src_lo
	bne _noCarry4
	inc src_hi
_noCarry4:

	txa
	; Flags count in tmp
	sta tmp

	lda dst_lo
	sta backptr_lo
	
	; This takes one more byte but one less cycle than e.g.:
	;	lda dst_hi
	;	sta backptr_hi
	;	dec backptr_hi
	clc
	lda dst_hi
	adc #$FF
	sta backptr_hi
	
	lda (backptr_lo),Y
	ldx #$00
	sta (dst_lo,X)
	
	inc dst_lo
	bne _noCarry5
	inc dst_hi
_noCarry5:

	lda dst_lo
	sta backptr_lo
	
	clc
	lda dst_hi
	adc #$FF
	sta backptr_hi
	
	lda (backptr_lo),Y
	ldx #$00
	sta (dst_lo,X)
	
	inc dst_lo
	bne _noCarry6
	inc dst_hi
_noCarry6:

	lda dst_lo
	sta backptr_lo
	
	clc
	lda dst_hi
	adc #$FF
	sta backptr_hi
	
	lda (backptr_lo),Y
	ldx #$00
	sta (dst_lo,X)

	inc dst_lo
	bne _noCarry7
	inc dst_hi
_noCarry7:

	lda tmp
	beq _unpack
	
_unpackloop:
	lda dst_lo
	sta backptr_lo
	
	clc
	lda dst_hi
	adc #$FF
	sta backptr_hi
	
	lda (backptr_lo),Y
	ldx #$00
	sta (dst_lo,X)

	inc dst_lo
	bne _noCarry8
	inc dst_hi
_noCarry8:

	; Decrease counter
	dec tmp
	bne _unpackloop
	
_unpack:
	jmp dounpack
