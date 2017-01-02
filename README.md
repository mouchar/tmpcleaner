Tmpcleaner
==========
Tmpcleaner is simply advanced temp cleaner with statistical capabilities.
It passes given structure only once, groups directories/files by given definition, applies different cleanup rules by each group and print final statistics.


Installation
------------
Tmpcleaner is compatible and tested with Python 2.6.6 and newer.

You can install it with PIP from Pypi:

	pip install tmpcleaner

Or directly from Github:

	pip install -e 'git://github.com/gooddata/tmpcleaner.git#egg=tmpcleaner'

Or from local GIT checkout:

	make install

Then you can run it by tmpcleaner.py script that is installed within package.

Usage
-----
Let's assume you have /tmp/app directory with some special huge structure, maybe on shared network filesystem where each operation is expensive. Now you want to clean it up and gather some statistics.

### Configuration
Configuration file should be simple YAML file.

#### Global options
| Parameter     | Description                                         |
| ------------- | --------------------------------------------------- |
| **pidfile**   | path to PID file, if empty, then PID won't be saved |
| **path**      | path to pass                                        |
| **pathIgnore**| regular expression for path to ignore, eg. `'.*/\.snapshot$'` to ignore directories named .snapshot |

#### Definition options
| Parameter     | Description                                                 |
| ------------- | ----------------------------------------------------------- |
| **name**      | friendly name for classification (otherwise id will be used |
| **pathMatch** | regular expression for path to match                        |
| **pathExclude** | regular expression for path to exclude                    |
| **noRemove**  | don't remove files/directories, only gather statistics      |
| **atime**     | filter by access time (hour)        |
| **mtime**     | Filter by modification time (hour)  |
| **ctime**     | filter by status change time (hour) |

#### Example
```
---
pidfile:    /var/run/tmpcleaner.pid
path:       /tmp/app
pathIgnore: '.*/\.snapshot(/.*|$)'

definitions:
	- # Always remove files named test when found
		name: test
		pathMatch: '.*/test$'
	- # Cleanup files that weren't modified for more than 1 day
		name: users
		pathMatch: '/tmp/app/users/.*'
		mtime: 24
	- # Never cleanup project directories, print just statistics
		name: projects
		pathMatch: '/tmp/app/projects/.*'
		noRemove: true
```

### Execution
Execute simply by running

	tmpcleaner.py /etc/tmpcleaner.yaml

Output will look like this, sizes are in bytes:

```
WARNING: Passing /tmp/app
WARNING: Summary: path=/tmp/app definition=temp removed_files=3 removed_dirs=0 removed_size=102400 existing_files=0 existing_dirs=0 existing_size=0
WARNING: Summary: path=/tmp/app definition=users removed_files=24 removed_dirs=4 removed_size=104857  existing_files=102 existing_dirs=1057 existing_size=1048576
WARNING: Summary: path=/tmp/app definition=projects removed_files=0 removed_dirs=0 removed_size=0 existing_files=52 existing_dirs=5 existing_size=16894
WARNING: Summary totals: path=/tmp/app time=27 time_pass=0 time_remove=0 removed_files=27 removed_dirs=4 removed_size=207257 existing_files=154 existing_dirs=1062 existing_size=1065470
```

Conclusion
----------
Now you should know how to simply setup and use Tmpcleaner.

Enjoy and feel free to contribute!
