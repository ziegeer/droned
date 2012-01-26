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

__doc__ = """This module defines custom exceptions used by DroneD.
   Typically these exceptions are used to encapsulate some data structure that
   provides details about the failure.
"""
from twisted.python.failure import Failure


class DroneCommandFailed(Exception):
    """Indicates a failed droned command, wraps the resultContext of the 
       failed command.
    """
    resultContext = {}

    def __init__(self, resultContext):
        self.resultContext = resultContext

    def __repr__(self):
        return 'DroneCommandFailed(%s)' % str(self.resultContext)
    __str__ = __repr__


class InvalidRelease(Exception):
    """Indicates a release operation could not be completed because the given
       release failed validation.
    """
    def __init__(self, release):
        Exception.__init__(self, "%s could not be validated" % release)
        self.release = release


class DeploymentNeeded(Exception):
    """Indicates that a release has not been fully deployed.
       Provides a missingInstalls dict that maps AppVersions and
       ConfigPackages to collections of Servers that they need to
       be installed on."""
    def __init__(self, missingInstalls):
        e = "%d applications have not been fully deployed" % \
                len(missingInstalls)
        Exception.__init__(self, e) 
        self.missingInstalls = missingInstalls


class PromotionNeeded(Exception):
    """Indicates that a release is not fully running. Includes
       list of instances onWrongRelease, list of instances running
       staleConfigs, and list of apps notRunning."""
    def __init__(self, onWrongRelease, staleConfigs, notRunning):
        self.onWrongRelease = onWrongRelease
        self.staleConfigs = staleConfigs
        self.notRunning = notRunning


class DeploymentFailed(Exception):
    """Indicates that a promotion operation failed. Provides a
       release attribute as well as a collection of failures."""
    def __init__(self, release, failures):
        e = "Deployment of %s encountered %d failures" % \
                (release,len(failures))
        Exception.__init__(self, e) 
        self.release = release
        self.failures = failures


class FormatError(Exception): pass


class ServiceNotAvailable(Exception):
    """Indicate that a service is missing or not available"""
    def __init__(self, name):
        Exception.__init__(self, 'no such service %s' % (name,))
        self.missingService = name
