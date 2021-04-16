"""
MIT Licence

Copyright (c) 2021 Fox Cunning

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""
__author__ = "Fox Cunning"
__credits__ = ["Fox Cunning",
               "Darren A.K.A. 'Phantasm' (C# implementation)",
               "Michael Dipperstein (hash key implementation)"]

from io import BytesIO
from pathlib import Path
import sys

WINDOW_SIZE = 256
MAX_UNENCODED = 2
MAX_CODED = MAX_UNENCODED + 256
HASH_SIZE = 1024


class FlagData:
    def __init__(self):
        pass

    flag_position: int = 0
    flags: int = 0
    next_encoded: int = 0


# ------------------------------------------------------------------------------

def update_flags(flag_data: FlagData, encoded_data: bytearray, writer: BytesIO):
    if flag_data.flag_position == 0x80:
        writer.write(flag_data.flags.to_bytes(1, "little"))
        for i in range(flag_data.next_encoded):
            writer.write(encoded_data[i].to_bytes(1, "little"))

        flag_data.flags = 0
        flag_data.flag_position = 1
        flag_data.next_encoded = 0

    else:
        flag_data.flag_position = flag_data.flag_position << 1


# ------------------------------------------------------------------------------

class EncodedString:
    def __init__(self):
        pass

    offset: int = 0
    length: int = 0


hash_table: list  # list = [0] * HASH_SIZE


# ------------------------------------------------------------------------------

def get_hash_key(data: any, offset: int) -> int:
    """This method generates a hash key for a (MAX_UNENCODED + 1)
       long string
    """
    hash_key: int = 0

    for i in range(0, MAX_UNENCODED + 1):
        hash_key = (hash_key << 5) ^ data[offset]
        hash_key = hash_key % HASH_SIZE
        offset = offset + 1

    return hash_key


# ------------------------------------------------------------------------------

def find_match(data: any, offset: int) -> EncodedString:
    """This method searches through the data or the longest sequence matching the MAX_CODED
       long string that is before the current offset
    """
    match_data = EncodedString()

    if offset > len(data) - (MAX_UNENCODED + 1):
        return match_data

    j = 0

    key_index = get_hash_key(data, offset)
    hash_key = hash_table[key_index]
    for i in hash_key:

        if i >= offset:
            continue

        if i < offset - WINDOW_SIZE:
            continue

        # First symbol matched
        if data[i] == data[offset]:

            j = 1

            while (offset + j) < len(data) and data[i + j] == data[offset + j]:
                if j >= MAX_CODED:
                    break
                j = j + 1

            if j > match_data.length:
                match_data.length = j
                match_data.offset = i

        if j >= MAX_CODED:
            match_data.length = MAX_CODED
            break

    return match_data


# ------------------------------------------------------------------------------

def encode(data: any) -> bytes:
    """
    Perform LZSS Algorithm Encoding
    """
    global hash_table

    writer = BytesIO()
    input_buffer = bytearray(data)

    length = len(input_buffer)
    if length == 0:
        return bytes(0)

    # Start with an empty list
    hash_table = list()
    for i in range(0, HASH_SIZE):
        hash_table.append([])

    flag_data = FlagData()

    # 8 code flags and 8 encoded strings
    flag_data.flags = 0
    flag_data.flag_position = 1
    encoded_data = bytearray(256 * 8)
    flag_data.next_encoded = 0  # Next index of encoded data

    input_buffer_position = 0  # Head of encoded lookahead

    for i in range(0, length - MAX_UNENCODED):
        hash_key = get_hash_key(input_buffer, i)
        hash_table[hash_key].append(i)

    match_data = find_match(input_buffer, input_buffer_position)

    while input_buffer_position < length:

        # Extend match length if trailing rubbish is present
        if input_buffer_position + match_data.length > length:
            match_data.length = length - input_buffer_position

        # Write unencoded byte if match is not long enough
        if match_data.length <= MAX_UNENCODED:

            match_data.length = 1  # 1 unencoded byte

            flag_data.flags = flag_data.flags | flag_data.flag_position  # Flag unencoded byte
            encoded_data[flag_data.next_encoded] = input_buffer[input_buffer_position]
            flag_data.next_encoded = flag_data.next_encoded + 1
            update_flags(flag_data, encoded_data, writer)

        # Encode as offset and length if match length >= max unencoded
        else:
            match_data.offset = (input_buffer_position - 1) - match_data.offset
            if match_data.offset > 255 or match_data.offset < 0:
                print("Match Data Offset out of range!")
                return bytes(0)
            if match_data.length - (MAX_UNENCODED + 1) > 255:
                print("Match Data Length out of range!")
                return bytes(0)

            encoded_data[flag_data.next_encoded] = match_data.offset
            flag_data.next_encoded = flag_data.next_encoded + 1

            encoded_data[flag_data.next_encoded] = match_data.length - (MAX_UNENCODED + 1)
            flag_data.next_encoded = flag_data.next_encoded + 1
            update_flags(flag_data, encoded_data, writer)

        input_buffer_position = input_buffer_position + match_data.length

        # Find next match
        match_data = find_match(input_buffer, input_buffer_position)

    # Write any remaining encoded data
    if flag_data.next_encoded != 0:
        writer.write(flag_data.flags.to_bytes(1, "little"))
        for i in range(0, flag_data.next_encoded):
            writer.write(encoded_data[i].to_bytes(1, "little"))

    return writer.getbuffer().tobytes(order='A')


# ----------------------------------------------------------------------------------------------------------------------

def decode(data: bytes, max_size: int = 4096) -> bytearray:
    """
    Performs LZSS decoding

    Parameters
    ----------
    data: bytes
        A string of bytes to decompress

    max_size: int
        Maximum size of uncompressed data, in bytes

    Returns
    -------
    bytearray
        A bytearray containing the uncompressed data
    """
    reader = BytesIO(data)
    length = len(reader.getbuffer())

    flags = 0  # Encoded flag
    flags_used = 7  # Unencoded flag

    out_data = bytearray()

    while len(out_data) < max_size:

        flags = flags >> 1
        flags_used = flags_used + 1

        # If all flag bits have been shifted out, read a new flag
        if flags_used == 8:

            if reader.tell() == length:
                break

            flags = reader.read(1)[0]
            flags_used = 0

        # Found an unencoded byte
        if (flags & 1) != 0:

            if reader.tell() == length:
                break

            out_data.append(reader.read(1)[0])

        # Found encoded data
        else:

            if reader.tell() == length:
                break

            code_offset = reader.read(1)[0]

            if reader.tell() == length:
                break

            code_length = reader.read(1)[0] + MAX_UNENCODED + 1

            for i in range(0, code_length):
                out_data.append(out_data[len(out_data) - (code_offset + 1)])

    return out_data


if __name__ == "__main__":
    if len(sys.argv) < 4:
        print(f"Usage: {sys.argv[0]} [c|u] <input filename> <output filename>")
        sys.exit(1)

    # Will decompress if False
    _compress = True

    if sys.argv[1] == 'u':
        _compress = False
    
    in_file = sys.argv[2]    
    out_file = sys.argv[3]

    if Path(out_file).exists():
        print(f"Output file '{out_file}' exists. Overwrite? (Y/N)",
              end='', flush=True)
        if input().lower().strip()[0] != 'y':
            print("Aborted.")
            sys.exit(0)
        
    print(f"{'Compressing' if _compress else 'Decompressing'} " +
          f"'{in_file}' to '{out_file}'...")

    try:
        fd = open(in_file, 'rb')
        data = fd.read()
        print(f"Data in: {len(data)} bytes.")
        fd.close()
    except IOError as error:
        print(f"Error reading '{in_file}': {error}")
        sys.exit(255)

    if _compress:
        compressed = encode(data)

        try:
            fd = open(out_file, 'wb')
            fd.write(compressed)
            print(f"Data out: {len(compressed)} bytes.")
            fd.close()
        except IOError as error:
            print(f"Error writing to '{out_file}': {error}")
            sys.exit(254)

        print(f"Compression ratio: {(100/len(data))*len(compressed):.2f}%")
        
    else:
        decompressed = decode(data, 65535)

        try:
            fd = open(out_file, 'wb')
            fd.write(decompressed)
            print(f"Data out: {len(decompressed)} bytes.")
            fd.close()
        except IOError as error:
            print(f"Error writing to '{out_file}': {error}")
            sys.exit(254)

    print("All done!")
    sys.exit(0)
