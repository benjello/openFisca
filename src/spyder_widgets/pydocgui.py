# -*- coding: utf-8 -*-
#
# Copyright © 2009-2010 Pierre Raybaut
# Licensed under the terms of the MIT License
# (see spyderlib/__init__.py for details)

"""pydoc widget"""

from src.qt.QtGui import QApplication, QCursor
from src.qt.QtCore import QThread, QUrl, Qt

import sys
import os.path as osp

# Local imports
from src.core.baseconfig import _
from src.spyder_widgets.browser import WebBrowser
from src.utils.misc import select_port


class PydocServer(QThread):
    """Pydoc server"""
    def __init__(self, port=7464):
        QThread.__init__(self)
        self.port = port
        self.server = None
        self.complete = False
        
    def run(self):
        import pydoc
        pydoc.serve(self.port, self.callback, self.completer)
        
    def callback(self, server):
        self.server = server
        
    def completer(self):
        self.complete = True
        
    def quit_server(self):
        self.server.quit = 1


class PydocBrowser(WebBrowser):
    """
    pydoc widget
    """
    DEFAULT_PORT = 30128
    
    def __init__(self, parent):
        WebBrowser.__init__(self, parent)
        self.server = None
        self.port = None
        
    def initialize(self):
        """Start pydoc server and load home page"""
        QApplication.setOverrideCursor(QCursor(Qt.WaitCursor))
        QApplication.processEvents()
        self.start_server()
        self.go_home()
        QApplication.restoreOverrideCursor()
        
    def is_server_running(self):
        """Return True if pydoc server is already running"""
        return self.server is not None
        
    def closeEvent(self, event):
        self.server.quit_server()
#        while not self.server.complete: #XXX Is it really necessary?
#            pass
        event.accept()
        
    #------ Public API -----------------------------------------------------
    def start_server(self):
        """Start pydoc server"""
        if self.server is None:
            self.port = select_port(default_port=self.DEFAULT_PORT)
            self.set_home_url('http://localhost:%d/' % self.port)
        elif self.server.isRunning():
            self.server.quit()
        self.server = PydocServer(port=self.port)
        self.server.start()

    #------ WebBrowser API -----------------------------------------------------
    def get_label(self):
        """Return address label text"""
        return _("Module or package:")
    
    def reload(self):
        """Reload page"""
        self.start_server()
        WebBrowser.reload(self)
        
    def text_to_url(self, text):
        """Convert text address into QUrl object"""
        if text.startswith('/'):
            text = text[1:]
        return QUrl(self.home_url.toString()+text+'.html')
    
    def url_to_text(self, url):
        """Convert QUrl object to displayed text in combo box"""
        return osp.splitext(unicode(url.path()))[0][1:]


def main():
    """Run web browser"""
    from spyderlib.utils.qthelpers import qapplication
    app = qapplication()
    widget = PydocBrowser(None)
    widget.show()
    widget.initialize()
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()