# -*- coding: utf-8 -*-

from PySide import QtGui

class StatusLabel(QtGui.QLabel):

    def __init__(self,parent=None):
        super(StatusLabel,self).__init__(parent)

    def minimumSizeHint(self):
        #sz = QtGui.QLabel.minimumSizeHint()
        sz = QtGui.QLabel.minimumSizeHint(self)
        sz.setWidth(0)
        return sz
