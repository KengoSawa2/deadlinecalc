# deadlinecalc

deadlinecalc is calculate fee from the rendering time on deadline with GUI.

![deadlinecalc](https://github.com/KengoSawa2/deadlinecalc/blob/master/SS/deadlinecalc.png "deadlinecalc")

## Overview

deadlinecalc provides the following functions.

- Easy calculate rendering fee
- Extract username and time range of rendering result
- Calculation algorithm is based on the score of cinebench.

All functions are implemented with "Deadline standalone Python API"
That is, deadlinecalc is front end tool.

deadlinecalc is in-house tool for L'espace Vision, it is a reference example program.
It is necessary to change the code directly for IP address, port number,etc....

Before you get started,You may study "Deadline standalone Python API"
https://docs.thinkboxsoftware.com/products/deadline/10.0/1_User%20Manual/manual/standalone-python.html

### Modification topic
important things necessary for change as you like.

- It is necessary to enter cinebench's score in slave information "Ex9" .
- By assigning a user name to each project, you can calculate the cost for each case.
- The user name must be following format.
  username_projectname
  If "_projectname" is none, total it with user name alone.
- QtCreator is necessary to change GUI with .ui file.

### License

Source Code license is [BSD 2-Clause License]  

### Environment

Windows10
deadline 10.0.xxxx

### Requitred Library

Pyside 1.2.x
knownpaths.py https://gist.github.com/mkropat/7550097

## Notice
This tool is in-house optimized implementation.
If you want to use at your company, you need to change the source code.
I think change is pretty easy, cheers!
