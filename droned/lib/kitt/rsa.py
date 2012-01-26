###############################################################################
#   Copyright 2006 to the present, Orbitz Worldwide, LLC.
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.
###############################################################################

import os
from ctypes import *
from ctypes.util import find_library

libc = CDLL( find_library("c") )
libcrypto = CDLL( find_library("crypto") )

# <stdio.h>
libc.fopen.argtypes = [c_char_p, c_char_p]
libc.fopen.restype = c_void_p
libc.fclose.argtypes = [c_void_p]
libc.fclose.restype = None

# <stdlib.h>
libc.malloc.argtypes = [c_int]
libc.malloc.restype = c_void_p
libc.free.argtypes = [c_void_p]
libc.free.restype = None

# <string.h>
libc.memcpy.argtypes = [c_void_p, c_void_p, c_int]
libc.memcpy.restype = c_void_p

# <openssl/PEM.h>
#RSA *PEM_read_RSAPrivateKey(FILE *fp, RSA **x, pem_password_cb *cb, void *u);
libcrypto.PEM_read_RSAPrivateKey.argtypes = [c_void_p] * 4
libcrypto.PEM_read_RSAPrivateKey.restype = c_void_p
#EVP_PKEY *PEM_read_PUBKEY(FILE *fp, EVP_PKEY **x, pem_password_cb *cb, void *u);
libcrypto.PEM_read_PUBKEY.argtypes = [c_void_p] * 4
libcrypto.PEM_read_PUBKEY.restype = c_void_p

# <openssl/evp.h>
libcrypto.EVP_PKEY_get1_RSA.argtypes = [c_void_p]
libcrypto.EVP_PKEY_get1_RSA.restype = c_void_p
libcrypto.EVP_PKEY_free.argtypes = [c_void_p]
libcrypto.EVP_PKEY_free.restype = c_void_p

# <openssl/rsa.h>
PADDING = 1 #value of RSA_PKCS1_PADDING on my system

for p in ('private','public'):
  for c in ('encrypt','decrypt'):
    func = getattr(libcrypto, "RSA_%s_%s" % (p,c))
    func.argtypes = [c_int, c_char_p, c_void_p, c_void_p, c_int]
    func.restype = c_int

libcrypto.RSA_size.argtypes = [c_void_p]
libcrypto.RSA_size.restype = c_int


class PrivateKey:
  def __init__(self, path):
    self.path = path
    self.id = os.path.basename(path).split('.',1)[0]
    fp = libc.fopen(path, "r")
    assert fp, "Cannot open file %s" % path
    rsa_key = libcrypto.PEM_read_RSAPrivateKey(fp, None, None, None)
    libc.fclose(fp)
    if libcrypto.ERR_peek_error() != 0 or not rsa_key:
      libcrypto.ERR_clear_error()
      if rsa_key:
        libcrypto.RSA_free(rsa_key)
      raise Exception("Failed to read RSA private key %s" % path)
    self.key = rsa_key

  def encrypt(self, text):
    return _process(text, libcrypto.RSA_private_encrypt, self.key)

  def decrypt(self, text):
    return _process(text, libcrypto.RSA_private_decrypt, self.key)


class PublicKey:
  def __init__(self, path):
    self.path = path
    self.id = os.path.basename(path)
    fp = libc.fopen(path, "r")
    assert fp, "Cannot open file %s" % path
    evp = libcrypto.PEM_read_PUBKEY(fp, None, None, None)
    libc.fclose(fp)
    if libcrypto.ERR_peek_error() != 0 or not evp:
      libcrypto.ERR_clear_error()
      if evp:
        libcrypto.EVP_PKEY_free(evp)
      raise Exception("Failed to read RSA public key %s" % path)

    rsa_key = libcrypto.EVP_PKEY_get1_RSA(evp)
    if libcrypto.ERR_peek_error() != 0 or not rsa_key:
      libcrypto.ERR_clear_error()
      libcrypto.EVP_PKEY_free(evp)
      #if rsa_key:
      #  libcrypto.RSA_free(rsa_key)
      raise Exception("Failed to extract RSA key from the EVP_PKEY at %s" % path)

    self.evp = evp
    self.key = rsa_key

    #FIXME
    # We are supposed to copy the RSA key out of our EVP structure
    # so we can properly manage memory. However this code crashes
    # indeterminently on some versions of libcrypto on 64-bit boxes.
    # I'm not paid to debug C code so I'm just gonna skip this step
    # to avoid the crashing at the cost of leaking about 100 bytes of
    # memory every time a PublicKey object is created. Boo hoo.
    #size = 88 # can't do libcrypto.RSA_size(rsa_key) because RSA_size != sizeof(RSA)
    #rsa_key2 = libc.malloc(size)
    #libc.memcpy(rsa_key2, rsa_key, size)
    #libcrypto.EVP_PKEY_free(evp)
    #self.key = rsa_key2

  def encrypt(self, text):
    return _process(text, libcrypto.RSA_public_encrypt, self.key)

  def decrypt(self, text):
    return _process(text, libcrypto.RSA_public_decrypt, self.key)


#The real magic happens here
def _process(source, func, key):
  dest = ""
  dest_buf_size = libcrypto.RSA_size(key)
  dest_buf = libc.malloc( dest_buf_size )
  assert dest_buf, "Failed to malloc. Damn."
  while source:
    read_len = min( len(source), dest_buf_size )
    i = func(read_len, source, dest_buf, key, PADDING)

    if i == -1 or libcrypto.ERR_peek_error():
      libcrypto.ERR_clear_error()
      libc.free(dest_buf)
      raise ValueError("Operation failed due to invalid input")

    dest += string_at(dest_buf, i)
    source = source[read_len:]

  libc.free(dest_buf)
  return dest
