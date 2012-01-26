%if ! (0%{?fedora} > 14 || 0%{?rhel} > 6)
#use classic sysv init scripts
%define systemd 0
%else
#use systemd hotness
%define systemd 1
%endif

Name:		droned
Version:        0.9.0
Release:	1%{?dist}
Summary:	DroneD - Application Service Framework	

Group:		System Environment/Daemons
License:	ASL 2.0
URL:		https://github.com/OrbitzWorldwide/droned
BuildArch:	noarch
Source0:	%{name}-%{version}.tar
BuildRoot:	%(mktemp -ud %{_tmppath}/%{name}-%{version}-%{release}-XXXXXX)

BuildRequires:	%{__python}
Requires:	python-twisted
Requires:	python-romeo
Requires(post):	openssl


%description
DroneD is a service container geared towards application management and monitoring.
It provides a rich API for implementing services and messaging interfaces. It is 
built on the Twisted Framework, and utilizes the BlasterProtocol and/or XMPP for 
network communication.


%package -n python-romeo
Summary:	Relational Object Mapping of Environmental Organization
Group:		Development/Languages
Requires:	PyYAML


%description -n python-romeo
Romeo: Relational Object Mapping of Environmental Organization

What is that supposed to mean? Romeo is built to provide programmatic 
access to information about the various components of an environment. What 
kind of components? Servers, applications, dependencies, and anything else you
can describe in terms of Key Value pairs. 

Question:
Isn't this the job of a CMDB?

Answer:
Find me a well documented CMDB API that is also an OSS CMDB that integrates 
well with DroneD and I will happily retire Romeo.


%package service
Summary:	DroneD management of SystemV Init Services
Group:		System Environment/Daemons
Requires:	%{name} = %{version}
#need for priv escalation, droned should not run as root
Requires:	usermode
#this next requires should be on every rh system by default
Requires:	rpm-python


%description service
DroneD pam and console.app security configuration to manage SystemV INIT
Services on a Linux system.  Should also work with systemd, but that isn't
as heavily tested at this point in time.


%prep
%setup -q


%build
for dir in %{name} romeo
do
  cd $dir
  %{__python} setup.py build
  cd ..
done

%install
for dir in %{name} romeo
do
  cd $dir
  %{__python} setup.py install \
      --root=$RPM_BUILD_ROOT \
      --record=INSTALLED_FILES \
      --optimize=1 #don't bytecode optimize rpmbuild will do it for us
  cd ..
done
#fix for brp_python_bytecompile on some systems
%{__mv} %{name}/INSTALLED_FILES %{name}/INSTALLED_FILES.orig
egrep -v '*.pyo|*.pyc' %{name}/INSTALLED_FILES.orig | \
	sed 's|\(.*.py\)$|\1*|' > \
	%{name}/INSTALLED_FILES

#for ROMEO configuration
%{__mkdir_p} $RPM_BUILD_ROOT%{_sysconfdir}/hostdb
#where to put daemon startup configuration
%{__mkdir_p} $RPM_BUILD_ROOT%{_sysconfdir}/%{name}
#for DroneD RSA keys, logging, and state storage
%{__mkdir_p} $RPM_BUILD_ROOT%{_sysconfdir}/pki/%{name}
%{__mkdir_p} $RPM_BUILD_ROOT/var/lib/%{name}

#make a log dir, can be used by droned's daemon maker
#even if systemd is present on the system.
%{__mkdir_p} $RPM_BUILD_ROOT/var/log/%{name}
%if %{systemd}
#install redhat systemd units
%{__install} -D contrib/redhat/%{name}.service \
	$RPM_BUILD_ROOT/lib/systemd/system/%{name}.service
%{__install} -D contrib/redhat/%{name}.target \
	$RPM_BUILD_ROOT/lib/systemd/system/%{name}.target
%else
#install redhat SysV init settings
%{__install} -D contrib/redhat/%{name}.init \
	$RPM_BUILD_ROOT%{_sysconfdir}/init.d/%{name}
#for now sysv and systemd are using external config for DroneD
%{__install} -D contrib/redhat/%{name}.sys \
	$RPM_BUILD_ROOT%{_sysconfdir}/sysconfig/%{name}
%endif

#install droned-service components from contrib
%{__install} -D -m 644 contrib/redhat/%{name}-service.pamd_service \
	$RPM_BUILD_ROOT%{_sysconfdir}/pam.d/service
%{__install} -D -m 644 contrib/redhat/%{name}-service.console_appssecurity_service \
	$RPM_BUILD_ROOT%{_sysconfdir}/security/console.apps/service

#install rpmdb aware application plugin
%{__install} -D -m 644 contrib/redhat/rh_service.py \
	$RPM_BUILD_ROOT%{_datadir}/%{name}/lib/%{name}/applications/rh_service.py

#hook service up to consolehelper
ln -sn %{_bindir}/consolehelper \
	$RPM_BUILD_ROOT%{_bindir}/service

#write basic start configuration
cat<<EOF_CONF > $RPM_BUILD_ROOT%{_sysconfdir}/%{name}/%{name}.conf
[droned]
homedir = /var/lib/droned
journal = /var/lib/droned/journal
umask = 0
maxfd = 1024
uid = nobody
gid = nobody
wait = 10
deadline = 30
logdir = /var/log/droned
EOF_CONF


%clean
rm -rf $RPM_BUILD_ROOT


%post
#echo "running post" #this runs even on updates :-/
#install (not upgrade)
#local keys should be private on every host, but don't assume everyone
#to have that policy. if the keys are already present, don't regenerate.
cd %{_sysconfdir}/pki/%{name}
if [ -r local.private -a -r local.public ]; then
    true
else   
    /usr/bin/openssl \
        genrsa \
        -out \
        local.private >&/dev/null
    /usr/bin/openssl \
        rsa \
        -in \
        local.private \
        -pubout \
        -out \
        local.public >&/dev/null
fi
%if %{systemd}
# units by default
/bin/systemctl is-active %{name}.service >/dev/null 2>&1 || :
if [ $1 -eq 0 ];then
    /bin/systemctl try-restart %{name}.service >/dev/null 2>&1 || :
else
    /bin/systemctl enable %{name}.service >/dev/null 2>&1 || :
fi
%else
/sbin/chkconfig --add %{name} >&/dev/null || :
%endif


%preun
#echo "running preun"
%if %{systemd}
# On uninstall (not upgrade), disable and stop the units
/bin/systemctl --no-reload disable %{name}.service >/dev/null 2>&1 || :
/bin/systemctl stop %{name}.service >/dev/null 2>&1 || :
%else
# On uninstall (not upgrade), disable and stop the init scripts
/sbin/service %{name} stop >/dev/null 2>&1 || :
/sbin/chkconfig %{name} off >&/dev/null || :
/sbin/chkconfig --del %{name} >&/dev/null || :
%endif


%postun
#echo "running postun"
%if %{systemd}
# Reload init system configuration, to make systemd honour changed
# or deleted unit files
/bin/systemctl daemon-reload >/dev/null 2>&1 || :
if [ $1 -ge 1 ] ; then
        # On upgrade (not uninstall), optionally, restart the daemon
        /bin/systemctl try-restart %{name}.service >/dev/null 2>&1 || :
fi
%endif


%files -f %{name}/INSTALLED_FILES
%defattr(-,root,root,-)
%doc LICENSE README NEWS
%dir %attr(755, root, root) %{_sysconfdir}/%{name}
%config(noreplace) %attr(600,root,root) %{_sysconfdir}/%{name}/%{name}.conf
%if %{systemd}
%config(noreplace) %attr(644,root,root) /lib/systemd/system/%{name}.service
%config(noreplace) %attr(644,root,root) /lib/systemd/system/%{name}.target
%else
%attr(755,root,root) %{_sysconfdir}/init.d/%{name}
%config(noreplace) %attr(644,root,root) %{_sysconfdir}/sysconfig/%{name}
%endif
%dir /var/log/%{name}
%dir %{_sysconfdir}/pki/%{name}
%dir %{_datadir}/%{name}
%dir /var/lib/%{name}


%files -n python-romeo -f romeo/INSTALLED_FILES
%defattr(-,root,root,-)
%doc LICENSE README NEWS romeo/example/*
%dir %{_sysconfdir}/hostdb


%files service
%defattr(-,root,root,-)
%doc LICENSE README NEWS contrib/redhat/%{name}-service.yaml
%{_bindir}/service
%config(noreplace) %{_sysconfdir}/pam.d/service
%config(noreplace) %{_sysconfdir}/security/console.apps/service
%{_datadir}/%{name}/lib/%{name}/applications/rh_service.py*
#so we don't collide with the base package
%exclude %dir %{_datadir}
%exclude %dir %{_datadir}/%{name}
%exclude %dir %{_datadir}/%{name}/lib
%exclude %dir %{_datadir}/%{name}/lib/%{name}
%exclude %dir %{_datadir}/%{name}/lib/%{name}/applications


%changelog
* Wed Jan 25 2012 Justin Venus <justin.venus@orbitz.com> 0.9.0-1
- getting ready to release open source.
- previous rpm changelog history has been removed to protect the innocent.
