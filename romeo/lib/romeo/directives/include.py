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

'''
Created on Jun 6, 2011

@author: cbrinley
'''
import os
import re
from romeo.directives import Directive,DirectiveException

class Include(Directive):
    name = "include"
    modes = ['pre']
    
    @classmethod
    def init_kwargs(cls,pp):
        imp = os.path.join(pp.root,"includes")
        ws = re.compile("^\s*")
        return {"includes_root":imp,
                "ws_re": ws
                }
    
    def is_valid(self):
        for line in self.get_lines():
            m = self.used_pattern.search(line)
            if not m: continue
            args = self.extract_args(line[m.start():m.end()])
            filepath = os.path.join(self.kwargs['includes_root'],args[0])
            try: self.find_circular_refs(filepath)
            except:
                self.data.seek(0) 
                raise #re-raise the original exception
                
    def find_circular_refs(self,target,files=None):
        '''locate circular references as name indicates
           if we see f1(include fX) ... fX(include f1)
           raise and exception otherwise exit silent. 
        '''
        if not files: files = [target]
        else: files.append(target)
        fd = open(target,'r')
        for line in fd:
            m = self.used_pattern.search(line)
            if not m: continue
            args = self.extract_args(line[m.start():m.end()])
            filepath = os.path.join(self.kwargs['includes_root'],args[0])
            if filepath in files:
                msg = "Circular reference while processing Romeo.include directive.\n"
                msg += "%s referenced more than once\n" % filepath
                msg += "include chain is as follows:\n"
                msg += " > ".join(files)
                raise DirectiveException(msg)
            else: self.find_circular_refs(filepath, files)
        
    
    def apply(self):
        out = []
        self.data.seek(0)
        for line in self.get_lines():
            m = self.used_pattern.search(line)
            if not m:
                out.append(line)
                continue
            args = self.extract_args(line[m.start():m.end()])
            filepath = os.path.join(self.kwargs['includes_root'],args[0])
            lines = self.build_content(line,filepath)
            out.extend(lines)
        return "".join(out)
    
    def get_starting_whitespace(self,line):
        m = self.kwargs['ws_re'].match(line)
        if not m: return ""
        return line[m.start():m.end()]
    
    def build_content(self,orig_line,filepath):
        '''#1 this should allow us to handle imports occuring at
              indented lines.
        '''
        m = self.used_pattern.search(orig_line)
        ws = self.get_starting_whitespace(orig_line) #1
        replaced = orig_line[m.start():m.end()]
        replicant = []
        fd = open(filepath,'r')
        for line in fd:
            m = self.used_pattern.search(line)
            if not m:
                store = ws+line
                #single space lines please.
                while store.endswith("\n\n"): store = store.replace("\n\n","\n") 
                replicant.append(ws+line)
                continue
            args = self.extract_args(line[m.start():m.end()])
            new_filepath = os.path.join(self.kwargs['includes_root'],args[0])
            replicant.extend( self.build_content(line,new_filepath) )
        first = replicant[0]
        replicant[0] = orig_line.replace(replaced,first)
        return replicant
            
            
