######################## BEGIN LICENSE BLOCK ########################
# The Original Code is mozilla.org code.
#
# The Initial Developer of the Original Code is
# Netscape Communications Corporation.
# Portions created by the Initial Developer are Copyright (C) 1998
# the Initial Developer. All Rights Reserved.
#
# Contributor(s):
#   Mark Pilgrim - port to Python
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2.1 of the License, or (at your option) any later version.
# 
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
# 
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA
# 02110-1301  USA
######################### END LICENSE BLOCK #########################

from constants import eStart, eError, eItsMe

# UCS2-BE

UCS2BE_cls = ( \
    0,0,0,0,0,0,0,0,  # 00 - 07 
    0,0,1,0,0,2,0,0,  # 08 - 0f 
    0,0,0,0,0,0,0,0,  # 10 - 17 
    0,0,0,3,0,0,0,0,  # 18 - 1f 
    0,0,0,0,0,0,0,0,  # 20 - 27 
    0,3,3,3,3,3,0,0,  # 28 - 2f 
    0,0,0,0,0,0,0,0,  # 30 - 37 
    0,0,0,0,0,0,0,0,  # 38 - 3f 
    0,0,0,0,0,0,0,0,  # 40 - 47 
    0,0,0,0,0,0,0,0,  # 48 - 4f 
    0,0,0,0,0,0,0,0,  # 50 - 57 
    0,0,0,0,0,0,0,0,  # 58 - 5f 
    0,0,0,0,0,0,0,0,  # 60 - 67 
    0,0,0,0,0,0,0,0,  # 68 - 6f 
    0,0,0,0,0,0,0,0,  # 70 - 77 
    0,0,0,0,0,0,0,0,  # 78 - 7f 
    0,0,0,0,0,0,0,0,  # 80 - 87 
    0,0,0,0,0,0,0,0,  # 88 - 8f 
    0,0,0,0,0,0,0,0,  # 90 - 97 
    0,0,0,0,0,0,0,0,  # 98 - 9f 
    0,0,0,0,0,0,0,0,  # a0 - a7 
    0,0,0,0,0,0,0,0,  # a8 - af 
    0,0,0,0,0,0,0,0,  # b0 - b7 
    0,0,0,0,0,0,0,0,  # b8 - bf 
    0,0,0,0,0,0,0,0,  # c0 - c7 
    0,0,0,0,0,0,0,0,  # c8 - cf 
    0,0,0,0,0,0,0,0,  # d0 - d7 
    0,0,0,0,0,0,0,0,  # d8 - df 
    0,0,0,0,0,0,0,0,  # e0 - e7 
    0,0,0,0,0,0,0,0,  # e8 - ef 
    0,0,0,0,0,0,0,0,  # f0 - f7 
    0,0,0,0,0,0,4,5)  # f8 - ff 

UCS2BE_st  = ( \
          5,     7,     7,eError,     4,     3,eError,eError,#00-07 
     eError,eError,eError,eError,eItsMe,eItsMe,eItsMe,eItsMe,#08-0f 
     eItsMe,eItsMe,     6,     6,     6,     6,eError,eError,#10-17 
          6,     6,     6,     6,     6,eItsMe,     6,     6,#18-1f 
          6,     6,     6,     6,     5,     7,     7,eError,#20-27 
          5,     8,     6,     6,eError,     6,     6,     6,#28-2f 
          6,     6,     6,     6,eError,eError,eStart,eStart)#30-37 

UCS2BECharLenTable = (2, 2, 2, 0, 2, 2)

UCS2BESMModel = {'classTable': UCS2BE_cls,
                 'classFactor': 6,
                 'stateTable': UCS2BE_st,
                 'charLenTable': UCS2BECharLenTable,
                 'name': 'UTF-16BE'}

# UCS2-LE

UCS2LE_cls = ( \
    0,0,0,0,0,0,0,0,  # 00 - 07 
    0,0,1,0,0,2,0,0,  # 08 - 0f 
    0,0,0,0,0,0,0,0,  # 10 - 17 
    0,0,0,3,0,0,0,0,  # 18 - 1f 
    0,0,0,0,0,0,0,0,  # 20 - 27 
    0,3,3,3,3,3,0,0,  # 28 - 2f 
    0,0,0,0,0,0,0,0,  # 30 - 37 
    0,0,0,0,0,0,0,0,  # 38 - 3f 
    0,0,0,0,0,0,0,0,  # 40 - 47 
    0,0,0,0,0,0,0,0,  # 48 - 4f 
    0,0,0,0,0,0,0,0,  # 50 - 57 
    0,0,0,0,0,0,0,0,  # 58 - 5f 
    0,0,0,0,0,0,0,0,  # 60 - 67 
    0,0,0,0,0,0,0,0,  # 68 - 6f 
    0,0,0,0,0,0,0,0,  # 70 - 77 
    0,0,0,0,0,0,0,0,  # 78 - 7f 
    0,0,0,0,0,0,0,0,  # 80 - 87 
    0,0,0,0,0,0,0,0,  # 88 - 8f 
    0,0,0,0,0,0,0,0,  # 90 - 97 
    0,0,0,0,0,0,0,0,  # 98 - 9f 
    0,0,0,0,0,0,0,0,  # a0 - a7 
    0,0,0,0,0,0,0,0,  # a8 - af 
    0,0,0,0,0,0,0,0,  # b0 - b7 
    0,0,0,0,0,0,0,0,  # b8 - bf 
    0,0,0,0,0,0,0,0,  # c0 - c7 
    0,0,0,0,0,0,0,0,  # c8 - cf 
    0,0,0,0,0,0,0,0,  # d0 - d7 
    0,0,0,0,0,0,0,0,  # d8 - df 
    0,0,0,0,0,0,0,0,  # e0 - e7 
    0,0,0,0,0,0,0,0,  # e8 - ef 
    0,0,0,0,0,0,0,0,  # f0 - f7 
    0,0,0,0,0,0,4,5)  # f8 - ff 

UCS2LE_st = ( \
          6,     6,     7,     6,     4,     3,eError,eError,#00-07 
     eError,eError,eError,eError,eItsMe,eItsMe,eItsMe,eItsMe,#08-0f 
     eItsMe,eItsMe,     5,     5,     5,eError,eItsMe,eError,#10-17 
          5,     5,     5,eError,     5,eError,     6,     6,#18-1f 
          7,     6,     8,     8,     5,     5,     5,eError,#20-27 
          5,     5,     5,eError,eError,eError,     5,     5,#28-2f 
          5,     5,     5,eError,     5,eError,eStart,eStart)#30-37 

UCS2LECharLenTable = (2, 2, 2, 2, 2, 2)

UCS2LESMModel = {'classTable': UCS2LE_cls,
                 'classFactor': 6,
                 'stateTable': UCS2LE_st,
                 'charLenTable': UCS2LECharLenTable,
                 'name': 'UTF-16LE'}

# UTF-8

UTF8_cls = ( \
    1,1,1,1,1,1,1,1,  # 00 - 07  #allow 0x00 as a legal value
    1,1,1,1,1,1,0,0,  # 08 - 0f 
    1,1,1,1,1,1,1,1,  # 10 - 17 
    1,1,1,0,1,1,1,1,  # 18 - 1f 
    1,1,1,1,1,1,1,1,  # 20 - 27 
    1,1,1,1,1,1,1,1,  # 28 - 2f 
    1,1,1,1,1,1,1,1,  # 30 - 37 
    1,1,1,1,1,1,1,1,  # 38 - 3f 
    1,1,1,1,1,1,1,1,  # 40 - 47 
    1,1,1,1,1,1,1,1,  # 48 - 4f 
    1,1,1,1,1,1,1,1,  # 50 - 57 
    1,1,1,1,1,1,1,1,  # 58 - 5f 
    1,1,1,1,1,1,1,1,  # 60 - 67 
    1,1,1,1,1,1,1,1,  # 68 - 6f 
    1,1,1,1,1,1,1,1,  # 70 - 77 
    1,1,1,1,1,1,1,1,  # 78 - 7f 
    2,2,2,2,3,3,3,3,  # 80 - 87 
    4,4,4,4,4,4,4,4,  # 88 - 8f 
    4,4,4,4,4,4,4,4,  # 90 - 97 
    4,4,4,4,4,4,4,4,  # 98 - 9f 
    5,5,5,5,5,5,5,5,  # a0 - a7 
    5,5,5,5,5,5,5,5,  # a8 - af 
    5,5,5,5,5,5,5,5,  # b0 - b7 
    5,5,5,5,5,5,5,5,  # b8 - bf 
    0,0,6,6,6,6,6,6,  # c0 - c7 
    6,6,6,6,6,6,6,6,  # c8 - cf 
    6,6,6,6,6,6,6,6,  # d0 - d7 
    6,6,6,6,6,6,6,6,  # d8 - df 
    7,8,8,8,8,8,8,8,  # e0 - e7 
    8,8,8,8,8,9,8,8,  # e8 - ef 
    10,11,11,11,11,11,11,11,  # f0 - f7 
    12,13,13,13,14,15,0,0)   # f8 - ff 

UTF8_st = ( \
    eError,eStart,eError,eError,eError,eError,     12,   10,#00-07 
         9,     11,     8,     7,     6,     5,     4,    3,#08-0f 
    eError,eError,eError,eError,eError,eError,eError,eError,#10-17 
    eError,eError,eError,eError,eError,eError,eError,eError,#18-1f 
    eItsMe,eItsMe,eItsMe,eItsMe,eItsMe,eItsMe,eItsMe,eItsMe,#20-27 
    eItsMe,eItsMe,eItsMe,eItsMe,eItsMe,eItsMe,eItsMe,eItsMe,#28-2f 
    eError,eError,     5,     5,     5,     5,eError,eError,#30-37 
    eError,eError,eError,eError,eError,eError,eError,eError,#38-3f 
    eError,eError,eError,     5,     5,     5,eError,eError,#40-47 
    eError,eError,eError,eError,eError,eError,eError,eError,#48-4f 
    eError,eError,     7,     7,     7,     7,eError,eError,#50-57 
    eError,eError,eError,eError,eError,eError,eError,eError,#58-5f 
    eError,eError,eError,eError,     7,     7,eError,eError,#60-67 
    eError,eError,eError,eError,eError,eError,eError,eError,#68-6f 
    eError,eError,     9,     9,     9,     9,eError,eError,#70-77 
    eError,eError,eError,eError,eError,eError,eError,eError,#78-7f 
    eError,eError,eError,eError,eError,     9,eError,eError,#80-87 
    eError,eError,eError,eError,eError,eError,eError,eError,#88-8f 
    eError,eError,    12,    12,    12,    12,eError,eError,#90-97 
    eError,eError,eError,eError,eError,eError,eError,eError,#98-9f 
    eError,eError,eError,eError,eError,    12,eError,eError,#a0-a7 
    eError,eError,eError,eError,eError,eError,eError,eError,#a8-af 
    eError,eError,    12,    12,    12,eError,eError,eError,#b0-b7 
    eError,eError,eError,eError,eError,eError,eError,eError,#b8-bf 
    eError,eError,eStart,eStart,eStart,eStart,eError,eError,#c0-c7 
    eError,eError,eError,eError,eError,eError,eError,eError)#c8-cf 

UTF8CharLenTable = (0, 1, 0, 0, 0, 0, 2, 3, 3, 3, 4, 4, 5, 5, 6, 6)

UTF8SMModel = {'classTable': UTF8_cls,
               'classFactor': 16,
               'stateTable': UTF8_st,
               'charLenTable': UTF8CharLenTable,
               'name': 'UTF-8'}
