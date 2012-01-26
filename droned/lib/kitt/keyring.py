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

import os, glob, rsa

class RSAKeyRing(object):
    def __init__(self,keydir):
        self.keydir = keydir
        self.publicKeys = {}
        self.privateKeys = {}
        self.reloadKeys()


    def reloadKeys(self):
        files = glob.glob('%s/*' % self.keydir)
        for file in files:
            name = os.path.split(file)[1]
            if name.endswith('.public') or name.endswith('.private'):
                name = name.split('.',1)[0]
            try: 
                self.publicKeys[name] = rsa.PublicKey(file)
            except: 
                pass
            try:
                self.privateKeys[name] = rsa.PrivateKey(file)
            except:
                pass

    def publicDecrypt(self,keyID,text):
        assert keyID in self.publicKeys, "Invalid KeyID"
        return self.publicKeys[keyID].decrypt(text)


    def publicEncrypt(self,keyID,text):
        assert keyID in self.publicKeys, "Invalid KeyID"
        return self.publicKeys[keyID].encrypt(text)


    def privateDecrypt(self,keyID,text):
        assert keyID in self.privateKeys, "Invalid KeyID"
        return self.privateKeys[keyID].decrypt(text)


    def privateEncrypt(self,keyID,text):
        assert keyID in self.privateKeys, "Invalid KeyID"
        return self.privateKeys[keyID].encrypt(text)
