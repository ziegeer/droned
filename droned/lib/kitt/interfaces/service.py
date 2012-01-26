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

from zope.interface import Interface, Attribute

class IDroneDService(Interface):
    """Used to define service modules iterface"""
    SERVICENAME = Attribute("""name of this service""")
    SERVICECONFIG = Attribute("""a dictionary to hold service configuration""")
    service = Attribute("""global service container object""")
    parentService = Attribute("""global reference to the application set by install method""")

    def install(_parentService):
        """should set _parentService as global parentService

           @return None
        """

    def start():
        """should set global service and call service.setName(SERVICENAME)
           and service.setServiceParent(parentService)

           Note: service objects must adhere to the interface of
           twisted.application.service.IService

           @return None
        """

    def stop():
        """should stop the service, call service.disownParentService and set
           service attribute to None

           @return None
        """

    def running():
        """check that service is running

           @return bool
        """

__all__ = ['IDroneDService']
