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


from pandas import DataFrame

from src.gui.qt.QtGui import (QWidget, QApplication, QCursor, QDockWidget)
from src.gui.qt.QtCore import SIGNAL, Qt

from src.gui.qthelpers import OfSs
from src.lib.utils import lorenz, gini

from src.widgets.matplotlibwidget import MatplotlibWidget

from src.gui.qthelpers import DataFrameViewWidget

from src.gui.qt.QtGui import QGroupBox, QVBoxLayout
from src.plugins.__init__ import OpenfiscaPluginWidget, PluginConfigPage
from src.gui.config import get_icon
from src.gui.baseconfig import get_translation
from src.lib.utils import mark_weighted_percentiles
_ = get_translation('inequality', 'src.plugins.survey')

from src.lib.utils import of_import


class InequalityConfigPage(PluginConfigPage):
    def __init__(self, plugin, parent):
        PluginConfigPage.__init__(self, plugin, parent)
        self.get_name = lambda: _("Inequality")
        
    def setup_page(self):

        group = QGroupBox(_("Lorenz curve"))
        
        #xaxis  
        
        vlayout = QVBoxLayout()
        vlayout.addWidget(group)
        vlayout.addStretch(1)
        self.setLayout(vlayout)


class InequalityWidget(OpenfiscaPluginWidget):
    """
    Distribution Widget
    """
    CONF_SECTION = 'inequality'
    CONFIGWIDGET_CLASS = InequalityConfigPage
    
    LOCATION = Qt.LeftDockWidgetArea
    FEATURES = QDockWidget.DockWidgetClosable | \
               QDockWidget.DockWidgetFloatable | \
               QDockWidget.DockWidgetMovable
    DISABLE_ACTIONS_WHEN_HIDDEN = False
    
    def __init__(self, parent = None):
        super(InequalityWidget, self).__init__(parent)
        self.setStyleSheet(OfSs.dock_style)
        # Create geometry
        self.dockWidgetContents = QWidget()
        
        widget_list = []

        self.lorenzWidget = MatplotlibWidget(self.dockWidgetContents,
                                              title= _("Lorenz curve"), # 'Courbe de Lorenz',
                                              xlabel= _('Population'), 
                                              ylabel= _('Variable'),
                                              hold=True,
                                              xlim = [0,1],
                                              ylim = [0,1])
        widget_list.append(self.lorenzWidget)
        self.ineqFrameWidget = DataFrameViewWidget(self.dockWidgetContents)
        widget_list.append(self.ineqFrameWidget)

        verticalLayout = QVBoxLayout(self.dockWidgetContents)
        for widget in widget_list:
            verticalLayout.addWidget(widget)
        self.setLayout(verticalLayout)

        # Initialize attributes
        self.parent = parent

        self.data = DataFrame() 
        self.data_default = None
        self.vars = {'nivvie_ini': ['men'],
                     'nivvie_net':  ['men'],                    
                     'nivvie' : ['men']}


        self.simulation = None
#        self.vars = {'nivvie_prim': ['ind', 'men'],
#                     'nivvie_init': ['ind', 'men'],
#                     'nivvie_net':  ['ind', 'men'],                    
#                     'nivvie' : ['ind', 'men']}
        

    #------ Public API ---------------------------------------------


    def plot(self):
        '''
        Plots the Lorenz Curve
        '''        
        axes = self.lorenzWidget.axes
        axes.clear()
            
        output = self.simulation.outputs
        WEIGHT = of_import(None, 'WEIGHT', self.simulation.country)

        entities = ['ind', 'men']
        weights = {}
        for entity in entities:
            weights[entity] = output._inputs.get_value(WEIGHT, entity)
        
        for varname, entities in self.vars.iteritems():
            for entity in entities:
            
                values  = output.get_value(varname, entity)
                
                x, y = lorenz(values, weights[entity])
                label = varname + ' (' + entity + ') ' 
                axes.plot(x,y, linewidth = 2, label = label)
                
        axes.plot(x,x, label ="")
        axes.legend(loc= 2, prop = {'size':'medium'})
        axes.set_xlim([0,1])
        axes.set_ylim([0,1])
        self.lorenzWidget.update()
            
    def set_simulation(self, simulation):
        '''
        Set the simulation
        
        Parameters
        ----------
        
        simulation : SurveySimulation
                     the simualtion object to extract the data from
        '''
        self.simulation = simulation 

        
    def update_frame(self):
        output = self.simulation.outputs
        final_df = None
        
        WEIGHT = of_import(None, 'WEIGHT', self.simulation.country)
        for varname, entities in self.vars.iteritems():
            for entity in entities:
                val  = output.get_value(varname, entity)
                weights = output._inputs.get_value(WEIGHT, entity)
                champm = output._inputs.get_value('champm', entity)

            items = []
            # Compute mean
            moy = (weights*champm*val).sum()/(weights*champm).sum()
            items.append( ("Moyenne",  [moy]))

            # Compute deciles
            labels = range(1,11)
            method = 2
            decile, values = mark_weighted_percentiles(val, labels, weights*champm, method, return_quantiles=True)
            
            labels = [ 'D'+str(d) for d in range(1,11)]
            del decile
            for l, v in zip(labels[:-1],values[1:-1]):
                items.append( (l, [v]))
        
            # Compute Gini
            gini_coeff = gini(val, weights*champm)
            items.append( ( _("Gini index"), [gini_coeff]))

            df = DataFrame.from_items(items, orient = 'index', columns = [varname])            
            df = df.reset_index()
            if final_df is None:
                final_df = df
            else:
                final_df = final_df.merge(df, on='index')
        
        final_df[u"Initial à net"] = (final_df['nivvie_net']-final_df['nivvie_ini'])/final_df['nivvie_ini']
        final_df[u"Net à disponible"] = (final_df['nivvie']-final_df['nivvie_net'])/final_df['nivvie_net']
        final_df = final_df[['index','nivvie_ini', u"Initial à net", 'nivvie_net',u"Net à disponible",'nivvie']]
        self.ineqFrameWidget.set_dataframe(final_df)
        self.ineqFrameWidget.reset()
        
    def calculated(self):
        self.emit(SIGNAL('calculated()'))
    
    #------ OpenfiscaPluginMixin API ---------------------------------------------
    #------ OpenfiscaPluginWidget API ---------------------------------------------

    def get_plugin_title(self):
        """
        Return plugin title
        Note: after some thinking, it appears that using a method
        is more flexible here than using a class attribute
        """
        return _("Inequality")

    
    def get_plugin_icon(self):
        """
        Return plugin icon (QIcon instance)
        Note: this is required for plugins creating a main window
              and for configuration dialog widgets creation
        """
        return get_icon('OpenFisca22.png')
            
    def get_plugin_actions(self):
        """
        Return a list of actions related to plugin
        Note: these actions will be enabled when plugin's dockwidget is visible
              and they will be disabled when it's hidden
        """
        raise NotImplementedError
    
    def register_plugin(self):
        """
        Register plugin in OpenFisca's main window
        """
        self.main.add_dockwidget(self)


    def refresh_plugin(self):
        '''
        Update Inequality Table
        '''
        self.starting_long_process(_("Refreshing inequality widget ..."))
        self.set_simulation(self.main.survey_simulation)
        self.update_frame()
        self.plot()
        self.ending_long_process(_("Inequality widget refreshed"))
    
    def closing_plugin(self, cancelable=False):
        """
        Perform actions before parent main window is closed
        Return True or False whether the plugin may be closed immediately or not
        Note: returned value is ignored if *cancelable* is False
        """
        return True
