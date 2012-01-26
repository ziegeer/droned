'''
Created on Jun 17, 2011

@author: cbrinley
Use this file to add your own template variables. 
Hopefully the way to do it is more or less self evident from these examples
Also see <eclipse>/plugins/org.python.pydev.jython_<version>/jysrc for more examples.
helpful links for key api info: 
https://github.com/aptana/Pydev/tree/f742ccc87a78a0dbf5fcd618561b3a91cdfbf5f5/plugins/org.python.pydev/src
http://help.eclipse.org/indigo/topic/org.eclipse.platform.doc.isv/reference/api/overview-summary.html
'''


import template_helper

if False:
    py_context_type = org.python.pydev.editor.templates.PyContextType    




def getModuleShortName(context):
    return context.getModuleName().split(".")[-1]

template_helper.AddTemplateVariable(py_context_type, 'module_shortname', 'Short of current module', getModuleShortName)       
