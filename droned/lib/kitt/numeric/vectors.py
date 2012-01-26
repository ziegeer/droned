'''
Created on Jun 13, 2011

@author: cbrinley
'''

from zope.interface import implements, Interface, Attribute
from kitt.decorators import raises
from kitt.util import ClassLoader

class TransformFailure(Exception):pass

class ISimpleVectorTransform(Interface):
    '''represents a transform on a simple one dimensional vector.
       for those with a deeper math background than I, this is closer to an array
       transform interface than a true vector. An interface should be defined.
       to handled datapoints over various other real and complex spaces. This
       will be deferred until need arises.
    '''
    TYPE = Attribute("<string>: specifies the type of transform. this should correspond to what is used in config.")
    def compute(vector):
        '''takes in a metric set and returns the transform of that set.'''
        

class SimpleVectorTransformLoader(ClassLoader):
    interface_type = ISimpleVectorTransform
    subloaders = []
 

class VectorTransform(object):
    implements(ISimpleVectorTransform)
    TYPE = "none"
    
    @raises(TransformFailure)
    def compute(self,vector):
        return vector
    
class SeriesAverage(VectorTransform):
    TYPE = "average"
    
    @raises(TransformFailure)
    def compute(self, vector):
        return [sum(vector) / len(vector)]
    
class SeriesSum(VectorTransform):
    TYPE = "sum"
    
    @raises(TransformFailure)
    def compute(self,vector):
        return [sum(vector)]
    
class SeriesMax(VectorTransform):
    TYPE = "max"
    
    @raises(TransformFailure)
    def compute(self,vector):
        return [max(vector)]
    
class SeriesMin(VectorTransform):
    TYPE = "min"
    
    @raises(TransformFailure)
    def compute(self,vector):
        return [min(vector)]
