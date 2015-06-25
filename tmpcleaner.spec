Name:		tmpcleaner
Version:	1.0.4
Release:	1%{?dist}
Source0:	tmpcleaner.tar.gz
License:	BSD
Summary:	Smart Temp Cleaner
Group:		Development/Libraries
BuildRoot:	%{_tmppath}/%{name}-%{version}-%{release}-buildroot
BuildArch:	noarch
Vendor:		GoodData Corporation <root@gooddata.com>
Requires:	PyYAML python-argparse python-dateutil
BuildRequires:	python2-devel python-setuptools-devel python-argparse PyYAML
Url:		https://github.com/gooddata/tmpcleaner
Obsoletes:	gdc-python-tools < 2

%description
Tmpcleaner is simply advanced temp cleaner with statistical capabilities.
It passes given structure only once, groups directories/files by given
definition, applies different cleanup rules by each group and print final
statistics.

%prep
%setup -q -n tmpcleaner

%build
python setup.py build

%install
%{__rm} -rf %{buildroot}
%{__python} setup.py install -O1 --skip-build --root %{buildroot}

%clean
%{__rm} -rf %{buildroot}

%files
%defattr(-,root,root,-)
%{python_sitelib}/*.egg-info
%{python_sitelib}/gdctmpcleaner
/usr/bin/tmpcleaner.py
