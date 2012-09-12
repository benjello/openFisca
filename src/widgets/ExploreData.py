# -*- coding:utf-8 -*-
# Copyright © 2012 Clément Schaff, Mahdi Ben Jelloul

"""
openFisca, Logiciel libre de simulation du système socio-fiscal français
Copyright © 2011 Clément Schaff, Mahdi Ben Jelloul

This file is part of openFisca.

    openFisca is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    openFisca is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with openFisca.  If not, see <http://www.gnu.org/licenses/>.
"""
from PyQt4.QtGui import (QWidget, QDockWidget, QLabel, QVBoxLayout, QHBoxLayout, QPushButton,
                         QSpacerItem, QSizePolicy, QApplication, QCursor, QInputDialog)
from PyQt4.QtCore import SIGNAL, Qt, QVariant
from core.qthelpers import OfSs, DataFrameViewWidget
from pandas import DataFrame
from core.qthelpers import MyComboBox
from core.columns import EnumCol


class ExploreDataWidget(QDockWidget):
    def __init__(self, parent = None):
        super(ExploreDataWidget, self).__init__(parent)
        self.setStyleSheet(OfSs.dock_style)
        # Create geometry
        self.setObjectName("ExploreData")
        self.setWindowTitle("ExploreData")
        self.dockWidgetContents = QWidget()
        
        data_label = QLabel(u"Data", self.dockWidgetContents)

        self.add_btn = QPushButton(u"Ajouter variable",self.dockWidgetContents)        
        self.remove_btn = QPushButton(u"Retirer variable",self.dockWidgetContents)  
        self.datatables_choices = []
        self.datatable_combo = MyComboBox(self.dockWidgetContents, u'Choix de la table', self.datatables_choices) 
        
#        self.add_btn.setDisabled(True)
#        self.remove_btn.setDisabled(True)
        
        spacerItem = QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)

        horizontalLayout = QHBoxLayout()
        horizontalLayout.addWidget(self.add_btn)
        horizontalLayout.addWidget(self.remove_btn)
        horizontalLayout.addWidget(self.datatable_combo)
        horizontalLayout.addItem(spacerItem)
        self.view = DataFrameViewWidget(self.dockWidgetContents)

        verticalLayout = QVBoxLayout(self.dockWidgetContents)
        verticalLayout.addWidget(data_label)

        verticalLayout.addLayout(horizontalLayout)
        verticalLayout.addWidget(self.view)
        self.setWidget(self.dockWidgetContents)

        # Initialize attributes
        self.parent = parent

        self.selected_vars = set()
        self.data = DataFrame() 
        self.view_data = None
        self.dataframes = {}
        self.vars = set()

        self.connect(self.add_btn, SIGNAL('clicked()'), self.add_var)
        self.connect(self.remove_btn, SIGNAL('clicked()'), self.remove_var)
        self.connect(self.datatable_combo.box, SIGNAL('currentIndexChanged(int)'), self.select_data)        

        self.update_btns()

    def update_btns(self):
        if (self.vars - self.selected_vars):
            self.add_btn.setEnabled(True)
        if self.selected_vars:
            self.remove_btn.setEnabled(True)
            
    def update_choices(self):
        box = self.datatable_combo.box
        box.clear()
        for name, key in self.datatables_choices:
            box.addItem(name, QVariant(key))

    def select_data(self):
        widget = self.datatable_combo.box
        dataframe_name = unicode(widget.itemData(widget.currentIndex()).toString())
        if dataframe_name: # to deal with the box.clear() 
            self.set_dataframe(name = dataframe_name)
        self.update_btns()

    def add_dataframe(self, dataframe, name = None):
        '''
        Adds a dataframe to the list o the available dataframe 
        '''
        if name == None:
            name = "dataframe" + len(self.dataframes.keys())
    
#        if not self.data:
#            self.dataframes = {}

        self.dataframes[name] = dataframe
        self.datatables_choices.append((name, name))
        self.update_choices()
        self.update_btns()

    def set_dataframe(self, dataframe = None, name = None):
        '''
        Sets the current dataframe
        '''
        if name is not None:
            self.data = self.dataframes[name]
        if dataframe is not None:
            self.data = dataframe
            
        self.vars = set(self.data.columns)
        self.update_btns()

    def ask(self, remove=False):
        if not remove:
            label = "Ajouter une variable"
            choices = self.vars - self.selected_vars
        else:
            choices =  self.selected_vars
            label = "Retirer une variable"
            
        var, ok = QInputDialog.getItem(self, label , "Choisir la variable", 
                                       sorted(list(choices)))
        if ok and var in list(choices): 
            return str(var)
        else:
            return None 

    def add_var(self):
        var = self.ask()
        if var is not None:
            self.selected_vars.add(var)
            self.update_view()
        else:
            return
    
    def remove_var(self):
        var = self.ask(remove=True)
        if var is not None:
            self.selected_vars.remove(var)
            self.update_view()
        else:
            return
                         
    def set_choices(self, description):
        '''
        Set the variables appearing in the add and remove dialogs 
        '''     
        data_vars = set(self.data.columns)
        label2var = {}
        var2label = {}
        var2enum = {}
        for var in description.col_names:
            varcol  = description.get_col(var)
            if isinstance(varcol, EnumCol): 
                var2enum[var] = varcol.enum
                if varcol.label:
                    label2var[varcol.label] = var
                    var2label[var]          = varcol.label
                else:
                    label2var[var] = var
                    var2label[var] = var
        
        all_labels = set(label2var.values()).intersection(data_vars)
        
        self.var2label = var2label
        self.var2enum  = var2enum
        
    def update_view(self):
        QApplication.setOverrideCursor(QCursor(Qt.WaitCursor))
        if not self.selected_vars:
            self.view.clear()
            QApplication.restoreOverrideCursor()
            return
        
        cols = self.selected_vars

        if self.view_data is None:
            self.view_data = self.data[list(cols)]
        
        new_col = cols - set(self.view_data)
        if new_col:
            self.view_data[list(new_col)] = self.data[list(new_col)] 
            df = self.view_data
        else:
            df = self.view_data[list(cols)]
    
        self.view.set_dataframe(df)

#        by_var_label = self.var2label[by_var]
#        dist_frame.insert(0,by_var_label,u"") 
#        enum = self.var2enum[by_var]
#        dist_frame[by_var_label] = dist_frame[by_var].apply(lambda x: enum._vars[x])
#        dist_frame.pop(by_var)
        self.view.reset()
        self.update_btns()
        QApplication.restoreOverrideCursor()
        
    def calculated(self):
        self.emit(SIGNAL('calculated()'))
                
    def clear(self):
        self.view.clear()
        self.data = None
        self.datatables_choices = []
        self.dataframes = {}
        self.update_btns()