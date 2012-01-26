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

import sys
import os
import types
import re
import traceback
from cStringIO import StringIO
from romeo import entity

class DirectiveException(Exception): pass

###############################################################################
# Private Class handles pre-processor directives of the form:
# ${ROMEO.<directive> <args>}
###############################################################################
class Preprocessor(entity.Entity):
    '''This represents the main interface to the directives preprocessor
       useage is pretty straight forward. Create a instance passing in
       the root directory where romeo configs can be found. call
       preprocessor.process(fd) on each file object loaded form the romeo
       root directory.        
    '''
    def __init__(self,rootdir):
        self.root = rootdir
        self.group_states = {}
        self.directives = [] #available directives
        self.load_directives([Directive])
        
    def load_directives(self,inherits):
        '''there has got to be a better way
           plugin pattern away!!!
           
           #1 this could be a comprehension but it'd be hard
              to read.
           #2 maybe we should put a dummy sys.modules in place
              while doing this to limit junk in the name space.
        '''
        m = self.__class__.__module__
        exclude = ['__init__.py']
        relpath = sys.modules[m].__file__
        reldir = os.path.split(relpath)[0]
        fulldir = os.path.realpath(reldir)
        pyfiles = []
        for f in os.listdir(fulldir): #1
            ff = os.path.join(fulldir,f)
            if os.path.isfile(ff): pyfiles.append(f)
        pyfiles = [f for f in pyfiles if f.endswith(".py")]
        pyfiles = [f for f in pyfiles if f not in exclude]
        pyfiles = [f[:-3] for f in pyfiles]
        candidates = []
        for py in pyfiles:
            m = __import__(py,globals(),locals(),"romeo.directives") #2
            for i in dir(m):
                attr = getattr(m,i)
                if not type(attr) == types.TypeType: continue
                matches = [cls for cls in inherits 
                           if issubclass(attr,cls)
                           if attr.__name__ != cls.__name__]
                if len(matches) == len(inherits): candidates.append(attr)
        for c in candidates:
            cinst = c( c.name,self.root,*c.init_args(self),**c.init_kwargs(self) )
            self.directives.append(cinst)       
        
    def _process(self,name,data,mode):
        '''name = filename or other ID for this processing chain
           data = the string to receive any processing
           mode = specify which processor phase currently pre or post
        '''
	td = data
        for d in self.directives:
            if not d.supports(mode): continue
            d.set_mode(mode)
            try: 
                d.load(name,data)
                if not d.is_used(): continue
                d.is_valid()
                data = d.apply()
                d.reset()
            except DirectiveException:
                d.reset()
                traceback.print_exc()
        return data
    
    def pre_process(self,fd,name):
        '''call this method to run all pre-processor directives
           against the file described by FD
           #1 due to fact that there is not guaranteed order of
              directive execution we keep running through our processing
              loop until no changes have been detected.
        '''
        data = fd.read()
        mdata = self._process(name, data, "pre")
        while mdata != data: #1
            data = mdata
            mdata = self._process(name,data,"pre")
        return mdata
    
    def post_process(self,obj,name):
        '''apply any post processing needed with actual output of
           structured data parser. modules may support one or both
           modes. 
        '''
        data = obj
        mdata = self._process(name, data, 'post')
        while mdata != data: #1
            data = mdata
            mdata = self._process(name,data,"post")
        return mdata
               
    def shutdown(self):
        del self.directives[:]
        for k in self.group_states.keys():
            del self.group_states[k]
        
    def get_group_state(self,groupID):
        '''cooperating directives can use group state
           to simplify individual code bases while allowing
           complex actions that require both pre and post
           processing or multiple passes over data.
           common example would be a directive that sets
           a marker in the pre phase and passes state
           to a post phase.
        '''
        if groupID in self.group_states:
            return self.group_states[groupID]
        else:
            self.group_states[groupID] = {}
	    return self.group_states[groupID]
        


class Directive(object):
    '''base class for all directives:
       class variable name does not have to be unique. 
       Be careful of collisions. Multiple directives with 
       same name can support overloading of directives or
       alternative signatures for the same logical directive 
       name.
    '''    name = "Directive" #this does not have to be unique. be careful of collisions
    modes = ["pre","post"]
    
    def __init__(self,name,rootdir,*args,**kwargs):
        '''setup state for your directive
        '''
        self.root = rootdir
        self.name = name
        self.args = args
        self.kwargs = kwargs
        self.data = None
        self.filename = None
        self.raw_pattern = "\$\{ROMEO\.%s.*\}" % self.name
        self.used_pattern = re.compile(self.raw_pattern)
        self.mode = "none"
    
    def supports(self,mode):
        return mode in self.modes
    
    def set_mode(self,mode):
        self.mode = mode 
        
    @classmethod
    def init_kwargs(cls,preprocessor):
        '''your closs has opportunity to generate its own
           kwargs, this will be passed to init if provided
           and saved as kwargs. what's the point of this?
           give your class opportunity to have a say in the
           way it is initialized. This function is also given
           a copy of the calling preprocessor. This can be used
           to determine if other Directives are being or have already
           been initialized among other uses. 
        '''
        return {}
    
    @classmethod
    def init_args(cls,preprocessor):
        '''same as init_args see its doc string.
        '''
        return []
        
    def extract_args(self,match_str):
        '''utility function to extract args from a "standard"
           directive definition. By "standard" we mean:
           ${ROMEO.foo arg1,arg2,...}
           a tuple of (arg1,arg2,...) will be returned.
        '''
        match = match_str.strip().replace("}","")
        match = match.split(" ")[1].strip()
        match = match.split(",")
        return tuple(match)
    
    def get_lines(self):
        '''utility provides iterator for 
           returning data line by line
        '''
        for line in self.data:
            yield line
        
    def load(self,filename,data):
        '''prepares this object to process data
           data is the only parameter and by default
           is stored at self.data
           #1 data should be file descriptor if not lets make it so
        '''
        self.filename = filename
        if type(data) == str:
            data = StringIO(data) #1
        self.data = data

    def reset(self):
        '''resets this instance to default state
           by default that just means clearing data
           variable.
        '''
        if hasattr(self.data,"close") and callable(self.data.close): 
            self.data.close()
        self.data = None
        self.filename = None
    
    def is_used(self):
        '''
            determine if this directive is used in the
            supplied data. only supported by default
            in the "pre" mode. if not in "pre" mode
            just return true. 
        '''
        if self.mode != "pre": return True
        strdata = self.data.read()
        self.data.seek(0)
        if self.used_pattern.search(strdata): return True
        else: return False
    
    def is_valid(self):
        '''determine if the directive has been used in a valid manner.
           Raises DirectiveException if not.
        '''
        msg = "Illegal use of abstract method. is_valid must be called from "
        msg += "a subclass of Directive that has a working implementation."
        raise DirectiveException(msg)
    
    def apply(self):
        '''actually apply the directive. this method should return
           the fully processed version of data which may be passed on 
           to other directives or passed back to romeo for yaml parsing.
        '''
        return self.data
