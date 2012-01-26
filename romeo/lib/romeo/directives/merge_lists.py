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
import re
from romeo.directives import Directive,DirectiveException



class PreMergeLists(Directive):
    '''This directive merges multiple lists into one list.
       Recommended to be used with be with your parser's anchor
       or tag system. here is a yaml example:
       
       SERVER:
         SERVICES: ${ROMEO.merge_lists *list1,*list2,*complex_type}
       MYLIST: &list1
         - item1
         - item2  
       ANOTHER: &list2
         - i3
         - i4 
       output without this directive:
       SERVER:
         SERVICES: [ [item1,item2],[i3,i4],*complex_type]
       output with this directive:  
       SERVER:
         SERVICES: [item1,item2,i3,i4,{comple:type}]
    '''
    name = "merge_lists"
    modes = ['pre']
    repl_pattern = '["$<ROMEO.merge_lists %s>", %s]'
    
    @classmethod
    def init_kwargs(cls, preprocessor):
        state = preprocessor.get_group_state("merge_lists")
        return {"group_state":state}
    
    def is_valid(self):
        '''for this directive we have no extended validation.
           we leave it up to the outer structured data parser
           to determine if our arguments are valid.
        '''
        return
    
    def apply(self):
        '''pre side of this directive basically just
           sets up some markers for the post side
           of the directive. that's where the heavy 
           lifting is at.
           #1 if we got this far we set state to true
              so post side of directive can quickly
              detect if we should continue processing.
        '''
        group_state = self.kwargs['group_state']
        group_state[self.filename] = True #1
        out = []
        self.data.seek(0)
        for line in self.get_lines():
            m = self.used_pattern.search(line)
            if not m:
                out.append(line)
                continue
            args = ", ".join( self.extract_args(line[m.start():m.end()]) )
            dirargs = ",".join( self.extract_args(line[m.start():m.end()]) )
            repl = self.repl_pattern % (dirargs,args)
            post_style_line = self.used_pattern.sub(repl,line,1)
            out.append(post_style_line)
        return "".join(out)
           
    
     

class PostMergeLists(Directive):
    '''Main logic is in merge_lists(). see its doc for details
       see PreMergLists for general directive notes.
    '''
    name = "merge_lists"
    modes = ['post']
    repl_pattern = '["$<ROMEO.merge_lists %s>", %s]'
    
    @classmethod
    def init_kwargs(cls, preprocessor):
        state = preprocessor.get_group_state('merge_lists')
        marker = re.compile("\$\<ROMEO\.%s.*\>" % cls.name )
        return {'group_state':state,
                 'marker': marker,
               }
    
    def is_used(self):
        '''traversing the whole dom could be quite expensive
           depending on how many tags and imports were used
           in raw source file. Our "pre" cousin has given us
           a way to check on the cheap.
        '''
        group_state = self.kwargs['group_state']
        return self.filename in group_state
    
    def is_valid(self):
        '''for this directive we have no extended validation.
           we leave it up to the outer structured data parser
           to determine if our arguments are valid.
        '''
        return
    
    def apply(self):
        self.used_pattern = self.kwargs['marker']
        td = type(self.data)
        if td == list: self.try_list_iterate(self.data)
        if td == dict: self.try_dict_iterate(self.data)
        del self.kwargs['group_state'][self.filename]
        return self.data
    
    def try_dict_iterate(self,data):
        for v in data.values():
            if type(v) == list:
                self.try_list_iterate(v)
            if type(v) == dict:
                self.try_dict_iterate(v)
    
    def try_list_iterate(self,data):
        #check list value 0
        #if its our guy merge it pluss next N lists
        #remove first N+1 lists
        #insert merged list as ord 0
        #iterate over list
        head = data[0]
        if type(head) == str and self.used_pattern.match(head):
            self.merge_lists(data)
        for i in data:
            if type(i) == list:
                self.try_list_iterate(i)
            if type(i) == dict:
                self.try_dict_iterate(i)
    
    def merge_lists(self,data):
        '''#1 figure out how many lists we should merge
              this is == to number of args passed to directive.
           #2 our total list len (of lists) must be at least as
              long as the number of args to our directive.
           #3 skip the directive string and get the arguments
              to the directive which should be the next <minlen>
              items in our parent list.
           #4 in case not all the items in our parent were
              themselves lists. make em lists.
           #5 flatten out this list of lists [[1],[2]] -> [1,2]
           #6 reverse our list so we have [2,1] and push these
              values onto the front of our list.
        '''
        err0 = 'merge_lists failed. '
        err0 += 'there are not enough input lists. '
        err0 += 'expected %s found %s.'
        head = data[0]
        args = self.extract_args(head) #1
        minlen = len(args) + 1
        actlen = len(data)
        if actlen < minlen: #2
            msg  = err0 % (minlen,actlen) 
            raise DirectiveException(msg)
        to_merge = data[1:minlen] #3
        for i in range(len(to_merge)): #4
            if type(to_merge[i]) != list:
                to_merge[i] = [to_merge[i]]
            i += 1
        out = []
        for l in to_merge: #5
            for i in l:
                out.append(i)
        del data[:minlen]
        out.reverse() #6
        for i in out:
            data.insert(0,i)
     

            
            
