# -*- coding:utf-8 -*-
# Copyright © 2011 Clément Schaff, Mahdi Ben Jelloul

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
from __future__ import division
import os
from xml.dom import minidom
from numpy import maximum as max_, minimum as min_
import numpy as np
from bisect import bisect_right
from Config import CONF, VERSION
import pickle
from datetime import datetime
from pandas import DataFrame


class Enum(object):
    def __init__(self, varlist, start = 0):
        self._vars = {}
        self._nums = {}
        self._count = 0
        for var in varlist:
            self._vars.update({self._count + start:var})
            self._nums.update({var: self._count + start})
            self._count += 1
            
    def __getitem__(self, var):
        return self._nums[var]

    def __iter__(self):
        return self.itervars()
    
    def itervars(self):
        for key, val in self._vars.iteritems():
            yield (val, key)
            
    def itervalues(self):
        for val in self._vars:
            yield val

def handle_output_xml(doc, tree, model, unit = 'men'):
    if doc.childNodes:
        for element in doc.childNodes:
            if element.nodeType is not element.TEXT_NODE:
                code = element.getAttribute('code')
                desc = element.getAttribute('desc')
                cols = element.getAttribute('color')
                short = element.getAttribute('shortname')
                typv = element.getAttribute('typevar')
                if cols is not '':
                    a = cols.rsplit(',')
                    col = (float(a[0]), float(a[1]), float(a[2]))
                else: col = (0,0,0)
                if typv is not '':
                    typv = int(typv)
                else: typv = 0
                child = OutNode(code, desc, color = col, typevar = typv, shortname=short)
                tree.addChild(child)
                handle_output_xml(element, child, model, unit)
    else:
        idx = model.index[unit]
        inputs = model._inputs
        enum = inputs.description.get_col('qui'+unit).enum
        people = [x[1] for x in enum]
        if tree.code in model.col_names:
            model.calculate(tree.code)
            val = model.get_value(tree.code, idx, opt = people, sum_ = True)
        elif tree.code in inputs.col_names:
            val = inputs.get_value(tree.code, idx, opt = people, sum_ = True)
        else:
            raise Exception('%s was not find in model nor in inputs' % tree.code)
        tree.setVals(val)

            
def gen_output_data(model):
    '''
    Generates output data according to totaux.xml
    '''    
    country = CONF.get('simulation', 'country')
    totals_fname = os.path.join(country,'totaux.xml')
    _doc = minidom.parse(totals_fname)

    tree = OutNode('root', 'root')

    handle_output_xml(_doc, tree, model)
    return tree

def gen_aggregate_output(model):

    out_dct = {}
    inputs = model._inputs
    unit = 'men'
    idx = model.index[unit]
    enum = inputs.description.get_col('qui'+unit).enum
    people = [x[1] for x in enum]

    model.calculate()

    varlist = set(['wprm', 'typ_men', 'so', 'typmen15', 'tu99', 'ddipl', 'ageq', 'cstotpragr', 'decile', 'champm'])
    for varname in model.col_names.union(varlist):
        if varname in model.col_names:
            if model.description.get_col(varname)._unit != unit:
                val = model.get_value(varname, idx, opt = people, sum_ = True)    
            else:
                val = model.get_value(varname, idx)
        elif varname in inputs.col_names:
            val = inputs.get_value(varname, idx)
        else:
            raise Exception('%s was not find in model nor in inputs' % varname)
        
        out_dct[varname] = val      
    # TODO: should take care the variables that shouldn't be summed automatically
    # MBJ: should we introduce a scope (men, fam, ind) in a the definition of columns ?
    
    

    out_table = DataFrame(out_dct)
    return out_table

class OutNode(object):
    def __init__(self, code, desc, shortname = '', vals = 0, color = (0,0,0), typevar = 0, parent = None):
        self.parent = parent
        self.children = []
        self.code = code
        self.desc = desc
        self.color = color
        self.visible = 0
        self.typevar = typevar
        self._vals = vals
        self._taille = 0
        if shortname: self.shortname = shortname
        else: self.shortname = code
        
    def addChild(self, child):
        self.children.append(child)
        if child.color == (0,0,0):
            child.color = self.color
        child.setParent(self)

    def setParent(self, parent):
        self.parent = parent

    def child(self, row):
        return(self.children[row])

    def childCount(self):
        return len(self.children)

    def row(self):
        if self.parent is not None:
            return self.parent.children.index(self)

    def setLeavesVisible(self):
        for child in self.children:
            child.setLeavesVisible()
        if (self.children and (self.code !='revdisp')) or (self.code == 'nivvie'):
            self.visible = 0
        else:
            self.visible = 1
    
    def partiallychecked(self):
        if self.children:
            a = True
            for child in self.children:
                a = a and (child.partiallychecked() or child.visible)
            return a
        return False
    
    def hideAll(self):
        if self.code == 'revdisp':
            self.visible = 1
        else:
            self.visible = 0
        for child in self.children:
            child.hideAll()
    
    def setHidden(self, changeParent = True):
        # les siblings doivent être dans le même
        if self.partiallychecked():
            self.visible = 0
            return
        for sibling in self.parent.children:
            sibling.visible = 0
            for child in sibling.children:
                child.setHidden(False)
        if changeParent:
            self.parent.visible = 1
                    
    def setVisible(self, changeSelf = True, changeParent = True):
        if changeSelf:
            self.visible = 1
        if self.parent is not None:
            for sibling in self.parent.children:
                if not (sibling.partiallychecked() or sibling.visible ==1):
                    sibling.visible = 1
            if changeParent:
                self.parent.setVisible(changeSelf = False)


    def getVals(self):
        return self._vals

    def setVals(self, vals):
        dif = vals - self._vals
        self._vals = vals
        self._taille = len(vals)
        if self.parent:
            self.parent.setVals(self.parent.vals + dif)
    
    vals = property(getVals, setVals)
        
    def __getitem__(self, key):
        if self.code == key:
            return self
        for child in self.children:
            val = child[key]
            if not val is None:
                return val
    
    def log(self, tabLevel=-1):
        output     = ""
        tabLevel += 1
        
        for i in range(tabLevel):
            output += "\t"
        
        output += "|------" + self.code + "\n"
        
        for child in self.children:
            output += child.log(tabLevel)
        
        tabLevel -= 1
        output += "\n"
        
        return output

    def __repr__(self):
        return self.log()

    def difference(self, other):
       
        self.vals -=  other.vals
        for child in self.children:
            child.difference(other[child.code])

    def __iter__(self):
        return self.inorder()
    
    def inorder(self):
        for child in self.children:
            for x in child.inorder():
                yield x
        yield self

class Scenario(object):
    def __init__(self):
        super(Scenario, self).__init__()
        self.year = CONF.get('simulation', 'datesim').year
        self.indiv = {}
        # indiv est un dict de dict. La clé est le noi de l'individu
        # Exemple :
        # 0: {'quifoy': 'vous', 'noi': 0, 'quifam': 'parent 1', 'noipref': 0, 'noidec': 0, 
        #     'birth': datetime.date(1980, 1, 1), 'quimen': 'pref', 'noichef': 0}
        self.declar = {}
        # declar est un dict de dict. La clé est le noidec.
        self.famille = {}
        
        # menage est un dict de dict la clé est la pref
        self.menage = {0:{'loyer':500,'so':3, 'code_postal':69001, 'zone_apl':2}}

        # on ajoute un individu, déclarant et chef de famille
        self.addIndiv(0, datetime(1975,1,1).date(), 'vous', 'chef')
    
    def check_consistency(self):
        '''
        Vérifie que le ménage entré est valide
        '''
        for noi, vals in self.indiv.iteritems():
            age = self.year - vals['birth'].year
            if age < 0:
                return u"L'année de naissance doit être antérieure à celle de la simulation (voir Fichier->Paramètres pour régler la date de la simulation"
            if vals['quifoy'] in ('vous', 'conj'):
                if age < 18: return u'Le déclarant et son éventuel conjoint doivent avoir plus de 18 ans'
            else:
                if age > 25 and (vals['inv']==0): return u'Les personnes à charges doivent avoir moins de 25 ans si elles ne sont pas invalides'
            if vals['quifoy'] == 'conj' and not vals['quifam'] == 'part':
                return u"Un conjoint sur la déclaration d'impôt doit être le partenaire dans la famille"
        return ''
    
    def modify(self, noi, newQuifoy = None, newFoyer = None):
        oldFoyer, oldQuifoy = self.indiv[noi]['noidec'], self.indiv[noi]['quifoy']
        if newQuifoy == None: newQuifoy = oldQuifoy
        if newFoyer == None: newFoyer = oldFoyer
        if oldQuifoy == 'vous':
            toAssign = self.getIndiv(oldFoyer, 'noidec')
            del self.declar[oldFoyer]
            self._assignPerson(noi, quifoy = newQuifoy, foyer = newFoyer)
            for person in toAssign:
                oldPos = self.indiv[person]['quifoy']
                if oldPos == "vous": continue
                else: self.modify(person, newQuifoy = oldPos, newFoyer = 0)
        else:
            self._assignPerson(noi, quifoy = newQuifoy, foyer = newFoyer)
        self.genNbEnf()

    def modifyFam(self, noi, newQuifam = None, newFamille = None):
        oldFamille, oldQuifam = self.indiv[noi]['noichef'], self.indiv[noi]['quifam']
        if newQuifam == None: newQuifam = oldQuifam
        if newFamille == None: newFamille = oldFamille
        if oldQuifam == 'chef':
            toAssign = self.getIndiv(oldFamille, 'noichef')
            del self.famille[oldFamille]
            self._assignPerson(noi, quifam = newQuifam, famille = newFamille)
            for person in toAssign:
                oldQui = self.indiv[person]['quifam']
                if oldQui == "chef": continue
                else: self.modifyFam(person, newQuifam = oldQui, newFamille = 0)
        else:
            self._assignPerson(noi, quifam = newQuifam, famille = newFamille)
        self.genNbEnf()
    
    def hasConj(self, noidec):
        '''
        Renvoie True s'il y a un conjoint dans la déclaration 'noidec', sinon False
        '''
        for vals in self.indiv.itervalues():
            if (vals['noidec'] == noidec) and (vals['quifoy']=='conj'):
                return True
        return False

    def hasPart(self, noichef):
        '''
        Renvoie True s'il y a un conjoint dans la déclaration 'noidec', sinon False
        '''
        for vals in self.indiv.itervalues():
            if (vals['noichef'] == noichef) and (vals['quifam']=='part'):
                return True
        return False
                
    def _assignVous(self, noi):
        ''' 
        Ajoute la personne numéro 'noi' et crée son foyer
        '''
        self.indiv[noi]['quifoy'] = 'vous'
        self.indiv[noi]['noidec'] = noi
        self.declar.update({noi:{}})

    def _assignConj(self, noi, noidec):
        ''' 
        Ajoute la personne numéro 'noi' à la déclaration numéro 'noidec' en tant 
        que 'conj' si declar n'a pas de conj. Sinon, cherche le premier foyer sans
        conjoint. Sinon, crée un nouveau foyer en tant que vous.
        '''
        decnum = noidec
        if (noidec not in self.declar) or self.hasConj(noidec):
            for k in self.declar:
                if not self.hasConj(k):
                    decnum = k
        if not self.hasConj(decnum):
            self.indiv[noi]['quifoy'] = 'conj'
            self.indiv[noi]['noidec'] = decnum
        else:
            self._assignVous(noi)

    def _assignPac(self, noi, noidec):
        ''' 
        Ajoute la personne numéro 'noi' et crée sa famille
        '''
        self.indiv[noi]['quifoy'] = 'pac0'
        self.indiv[noi]['noidec'] = noidec

    def _assignChef(self, noi):
        ''' 
        Ajoute la personne numéro 'noi' à la famille numéro 'declar' en tant
        que 'vous' et crée un conjoint vide si necéssaire
        '''
        self.indiv[noi]['quifam'] = 'chef'
        self.indiv[noi]['noichef'] = noi
        self.famille.update({noi:{}})

    def _assignPart(self, noi, noichef):
        ''' 
        Ajoute la personne numéro 'noi' à la déclaration numéro 'noidec' en tant 
        que 'conj' si declar n'a pas de conj. Sinon, cherche le premier foyer sans
        conjoint. Sinon, crée un nouveau foyer en tant que vous.
        '''
        famnum = noichef
        if (noichef not in self.famille) or self.hasPart(noichef):
            for k in self.famille:
                if not self.hasPart(k):
                    famnum = k
        if not self.hasPart(famnum):
            self.indiv[noi]['quifam'] = 'part'
            self.indiv[noi]['noichef'] = famnum
        else:
            self._assignChef(noi)

    def _assignEnfF(self, noi, noichef):
        ''' 
        Ajoute la personne numéro 'noi' à la déclaration numéro 'noidec' en tant
        que 'pac'
        '''
        self.indiv[noi]['quifam'] = 'enf0'
        self.indiv[noi]['noichef'] = noichef

    def _assignPerson(self, noi, quifoy = None, foyer = None, quifam = None, famille = None):
        if quifoy is not None:
            if   quifoy     == 'vous': self._assignVous(noi)
            elif quifoy     == 'conj': self._assignConj(noi, foyer)
            elif quifoy[:3] == 'pac' : self._assignPac(noi, foyer)
        if quifam is not None:
            if   quifam     == 'chef': self._assignChef(noi)
            elif quifam     == 'part': self._assignPart(noi, famille)
            elif quifam[:3] == 'enf' : self._assignEnfF(noi, famille)
        self.genNbEnf()

    def rmvIndiv(self, noi):
        oldFoyer, oldQuifoy = self.indiv[noi]['noidec'], self.indiv[noi]['quifoy']
        oldFamille, oldQuifam = self.indiv[noi]['noichef'], self.indiv[noi]['quifam']
        if oldQuifoy == 'vous':
            toAssign = self.getIndiv(oldFoyer, 'noidec')
            for person in toAssign:
                if self.indiv[person]['quifoy']     == 'conj': self._assignPerson(person, quifoy = 'conj', foyer = 0)
                if self.indiv[person]['quifoy'][:3] == 'pac' : self._assignPerson(person, quifoy = 'pac' , foyer = 0)
            del self.declar[noi]
        if oldQuifam == 'chef':
            toAssign = self.getIndiv(oldFamille, 'noichef')
            for person in toAssign:
                if self.indiv[person]['quifam']     == 'part': self._assignPerson(person, quifam = 'part', famille = 0)
                if self.indiv[person]['quifam'][:3] == 'enf' : self._assignPerson(person, quifam = 'enf' , famille = 0)
            del self.famille[noi]
        del self.indiv[noi]
        self.genNbEnf()

    def getIndiv(self, noi, champ = 'noidec'):
        for person, vals in self.indiv.iteritems():
            if vals[champ] == noi:
                yield person

    def addIndiv(self, noi, birth, quifoy, quifam):
        self.indiv.update({noi:{'birth':birth, 
                                'inv': 0,
                                'alt':0,
                                'activite':0,
                                'quifoy': 'none',
                                'quifam': 'none',
                                'noidec':  0,
                                'noichef': 0,
                                'noipref': 0}})

        self._assignPerson(noi, quifoy = quifoy, foyer = 0, quifam = quifam, famille = 0)
        self.updateMen()

    def nbIndiv(self):
        return len(self.indiv)
            
    def genNbEnf(self):
        for noi, vals in self.indiv.iteritems():
            if vals.has_key('statmarit'):
                statmarit = vals['statmarit']
            else: statmarit = 2
            if self.hasConj(noi) and (noi == vals['noidec']) and not statmarit in (1,5):
                statmarit = 1
            elif not self.hasConj(noi) and (noi == vals['noidec']) and not statmarit in (2,3,4):
                statmarit = 2
            # si c'est un conjoint, même statmarit que 'vous'
            if vals['quifoy'] == 'conj':
                statmarit = self.indiv[vals['noidec']]['statmarit']
            vals.update({'statmarit':statmarit})
                
        for noidec, vals in self.declar.iteritems():
            vals.update(self.NbEnfFoy(noidec))
        for noichef, vals in self.famille.iteritems():
            self.NbEnfFam(noichef)

    def NbEnfFoy(self, noidec):
        out = {'nbF': 0, 'nbG':0, 'nbH':0, 'nbI':0, 'nbR':0, 'nbJ':0, 'nbN':0}
        n = 0
        for vals in self.indiv.itervalues():
            if (vals['noidec']==noidec) and (vals['quifoy'][:3]=='pac'):
                n += 1
                if (self.year - vals['birth'].year >= 18) and vals['inv'] == 0: out['nbJ'] += 1
                else:
                    if   vals['alt'] == 0: 
                        out['nbF'] += 1
                        if vals['inv'] == 1 : out['nbG'] +=1
                    elif vals['alt'] == 1: 
                        out['nbH'] += 1
                        if vals['inv'] == 1: out['nbI'] += 1
                vals['quifoy'] = 'pac%d' % n
        return out

    def NbEnfFam(self, noichef):
        n = 0
        for vals in self.indiv.itervalues():
            if (vals['noichef']==noichef) and (vals['quifam'][:3]=='enf'):
                n += 1
                vals['quifam'] = 'enf%d' % n

    def updateMen(self):
        '''
        Il faut virer cela
        '''
        people = self.indiv
        for noi in xrange(self.nbIndiv()):
            if   noi == 0: quimen = 'pref'
            elif noi == 1: quimen = 'cref'
            else:  quimen = 'enf%d' % (noi-1)
            people[noi].update({'quimen': quimen,
                                'noipref': 0})

    def __repr__(self):
        outstr = "INDIV" + '\n'
        for key, val in self.indiv.iteritems():
            outstr += str(key) + str(val) + '\n'
        outstr += "DECLAR" + '\n'
        for key, val in self.declar.iteritems():
            outstr += str(key) + str(val) + '\n'
        outstr += "FAMILLE" + '\n'
        for key, val in self.famille.iteritems():
            outstr += str(key) + str(val) + '\n'
        outstr += "MENAGE" + '\n'
        for key, val in self.menage.iteritems():
            outstr += str(key) + str(val) + '\n'
        return outstr

    def saveFile(self, fileName):
        outputFile = open(fileName, 'wb')
        pickle.dump({'version': VERSION, 'indiv': self.indiv, 'declar': self.declar, 'famille': self.famille, 'menage': self.menage}, outputFile)
        outputFile.close()
    
    def openFile(self, fileName):
        inputFile = open(fileName, 'rb')
        S = pickle.load(inputFile)
        inputFile.close()
        self.indiv = S['indiv']
        self.declar = S['declar']
        self.famille = S['famille']
        self.menage = S['menage']


############################################################################
## Bareme and helper functions for Baremes
############################################################################

class Bareme(object):
    '''
    Object qui contient des tranches d'imposition en taux marginaux et en taux moyen
    '''
    def __init__(self, name = 'untitled Bareme'):
        super(Bareme, self).__init__()
        self._name = name
        self._tranches = []
        self._nb = 0
        self._tranchesM = []
        # if _linear_taux_moy is 'False' (default), the output is computed with a constant marginal tax rate in each bracket
        # set _linear_taux_moy to 'True' to compute the output with a linear interpolation on average tax rate
        self._linear_taux_moy = False

    @property
    def nb(self):
        return self._nb
    
    @property
    def seuils(self):
        return [x[0] for x in self._tranches]

    @property
    def taux(self):
        return [x[1] for x in self._tranches]

    def setSeuil(self, i, value):
        self._tranches[i][0] = value
        self._tranches.sort()

    def setTaux(self, i, value):
        self._tranches[i][1] = value

    @property
    def seuilsM(self):
        return [x[0] for x in self._tranchesM]

    @property
    def tauxM(self):
        return [x[1] for x in self._tranchesM]

    def setSeuilM(self, i, value):
        self._tranchesM[i][0] = value
        self._tranchesM.sort()

    def setTauxM(self, i, value):
        self._tranchesM[i][1] = value
    
    
    def multTaux(self, factor):
        for i in range(self.getNb()):
            self.setTaux(i,factor*self.taux[i])

    def multSeuils(self, factor):
        '''
        Returns a new instance of Bareme with scaled 'seuils' and same 'taux'
        '''
        b = Bareme(self._name)
        for i in range(self.nb):
            b.addTranche(factor*self.seuils[i], self.taux[i])
        return b
        
    def addBareme(self, bareme):
        if bareme.nb>0: # Pour ne pas avoir de problèmes avec les barèmes vides
            for seuilInf, seuilSup, taux  in zip(bareme.seuils[:-1], bareme.seuils[1:] , bareme.taux):
                self.combineTranche(taux, seuilInf, seuilSup)
            self.combineTranche(bareme.taux[-1],bareme.seuils[-1])  # Pour traiter le dernier seuil

    def combineTranche(self, taux, seuilInf=0, seuilSup=False ):
        # Insertion de seuilInf et SeuilSup sans modfifer les taux
        if not seuilInf in self.seuils:
            index = bisect_right(self.seuils, seuilInf)-1
            self.addTranche(seuilInf, self.taux[index]) 
        
        if seuilSup and not seuilSup in self.seuils:
                index = bisect_right(self.seuils,seuilSup)-1
                self.addTranche(seuilSup, self.taux[index]) 

        # On utilise addTranche pour ajouter les taux où il le faut        
        i = self.seuils.index(seuilInf)
        if seuilSup: j = self.seuils.index(seuilSup)-1 
        else: j = self._nb-1
        while (i <= j):
            self.addTranche(self.seuils[i], taux)
            i +=1
            
    def addTranche(self, seuil, taux):
        if seuil in self.seuils:
            i = self.seuils.index(seuil)
            self.setTaux(i, self.taux[i] + taux)
        else:
            self._tranches.append([seuil,taux])
            self._tranches.sort()
            self._nb = len(self._tranches)

    def rmvTranche(self):
        self._tranches.pop()
        self._nb = len(self._tranches)

    def addTrancheM(self, seuil, taux):
        if seuil in self.seuilsM:
            i = self.seuilsM.index(seuil)
            self.setTauxM(i, self.tauxM[i] + taux)
        else:
            self._tranchesM.append([seuil,taux])
    
    def marToMoy(self):
        self._tranchesM = []
        I, k = 0, 0
        if self.nb > 0:
            for seuil, taux in self:
                if k == 0:
                    sprec = seuil
                    tprec = taux
                    k += 1
                    continue            
                I += tprec*(seuil - sprec)
                self.addTrancheM(seuil, I/seuil)
                sprec = seuil
                tprec = taux
            self.addTrancheM('Infini', taux)

    def moyToMar(self):
        self._tranches = []
        Iprev, sprev = 0, 0
        z = zip(self.seuilsM, self.tauxM)
        for seuil, taux in z:
            if not seuil == 'Infini':
                I = taux*seuil
                self.addTranche(sprev, (I-Iprev)/(seuil-sprev))
                sprev = seuil
                Iprev = I
        self.addTranche(sprev, taux)
    
    def inverse(self):
        '''
        Returns a new instance of Bareme
        Inverse un barème: étant donné des tranches et des taux exprimés en fonction
        du brut, renvoie un barème avec les tranches et les taux exprimé en net.
          si revnet  = revbrut - BarmMar(revbrut, B)
          alors revbrut = BarmMar(revnet, B.inverse())
        seuil : seuil de revenu brut
        seuil imposable : seuil de revenu imposable/déclaré
        theta : ordonnée à l'origine des segments des différentes tranches dans une 
                représentation du revenu imposable comme fonction linéaire par 
                morceaux du revenu brut
        '''
        inverse = Bareme(self._name + "'")  # En fait 1/(1-taux_global)
        seuilImp, taux = 0, 0
        for seuil, taux in self:
            if seuil==0: theta, tauxp = 0,0
            # On calcul le seuil de revenu imposable de la tranche considérée
            seuilImp = (1-tauxp)*seuil + theta    
            inverse.addTranche(seuilImp, 1/(1-taux))
            theta = (taux - tauxp)*seuil + theta
            tauxp = taux # taux précédent
        return inverse
    
    def __iter__(self):
        self._seuilsIter = iter(self.seuils)
        self._tauxIter = iter(self.taux)
        return self

    def next(self):
        return self._seuilsIter.next(), self._tauxIter.next()
    
    def __str__(self):
        output = self._name + '\n'
        for i in range(self._nb):
            output += str(self.seuils[i]) + '  ' + str(self.taux[i]) + '\n'
        return output

    def __eq__(self, other):
        return self._tranches == other._tranches

    def __ne__(self, other):
        return self._tranches != other._tranches
    
    def calc(self, assiette, getT = False):
        '''
        Calcule un impôt selon le barême non linéaire exprimé en tranches de taux marginaux.
        'assiette' est l'assiette de l'impôt, en colonne;
        '''
        k = self.nb
        n = len(assiette)
        if not self._linear_taux_moy:
            assi = np.tile(assiette, (k, 1)).T
            seui = np.tile(np.hstack((self.seuils, np.inf)), (n, 1))
            a = max_(min_(assi, seui[:, 1:]) - seui[:,:-1], 0)
            i = np.dot(self.taux,a.T)
            if getT:
                t = np.squeeze(max_(np.dot((a>0), np.ones((k, 1)))-1, 0))
                return i, t
            else:
                return i
        else:
            if len(self.tauxM) == 1:
                i = assiette*self.tauxM[0]
            else:
                assi = np.tile(assiette, (k-1, 1)).T
                seui = np.tile(np.hstack(self.seuils), (n, 1))
                k = self.t_x().T
                a = (assi >= seui[:,:-1])*(assi < seui[:, 1:])
                A = np.dot(a, self.t_x().T)
                B = np.dot(a, np.array(self.seuils[1:]))
                C = np.dot(a, np.array(self.tauxM[:-1]))
                i = assiette*(A*(assiette-B) + C) + max_(assiette - self.seuils[-1], 0)*self.tauxM[-1] + (assiette >= self.seuils[-1])*self.seuils[-1]*self.tauxM[-2]
            if getT:
                t = np.squeeze(max_(np.dot((a>0), np.ones((k, 1)))-1, 0))
                return i, t
            else:
                return i

    def t_x(self):
        s = self.seuils
        t = [0]
        t.extend(self.tauxM[:-1])
        s = np.array(s)
        t = np.array(t)
        return (t[1:]-t[:-1])/(s[1:]-s[:-1])



def combineBaremes(BarColl, name="onsenfout"):
    '''
    Combine all the Baremes in the BarColl in a signle Bareme
    '''
    baremeTot = Bareme(name=name)
    baremeTot.addTranche(0,0)
    for val in BarColl.__dict__.itervalues():
        if isinstance(val, Bareme):
            baremeTot.addBareme(val)
        else: 
            combineBaremes(val, baremeTot)
    return baremeTot

class Object(object):
    def __init__(self):
        object.__init__(self)

def scaleBaremes(BarColl, factor):
    '''
    Scales all the Bareme in the BarColl
    '''
    if isinstance(BarColl, Bareme):
        return BarColl.multSeuils(factor)
    out = Object()
    from parametres.paramData import Tree2Object
    for key, val in BarColl.__dict__.iteritems():
        if isinstance(val, Bareme):
            setattr(out, key, val.multSeuils(factor))
        elif isinstance(val, Tree2Object):
            setattr(out, key, scaleBaremes(val, factor))
        else:
            setattr(out, key, val)
    return out

############################################################################
## Helper functions for stats
############################################################################
# from http://pastebin.com/KTLip9ee
def mark_weighted_percentiles(a, labels, weights, method, return_quantiles=False):
# a is an input array of values.
# weights is an input array of weights, so weights[i] goes with a[i]
# labels are the names you want to give to the xtiles
# method refers to which weighted algorithm. 
#      1 for wikipedia, 2 for the stackexchange post.

# The code outputs an array the same shape as 'a', but with
# labels[i] inserted into spot j if a[j] falls in x-tile i.
# The number of xtiles requested is inferred from the length of 'labels'.


# First method, "vanilla" weights from Wikipedia article.
    if method == 1:
    
        # Sort the values and apply the same sort to the weights.
        N = len(a)
        sort_indx = np.argsort(a)
        tmp_a = a[sort_indx].copy()
        tmp_weights = weights[sort_indx].copy()
    
        # 'labels' stores the name of the x-tiles the user wants,
        # and it is assumed to be linearly spaced between 0 and 1
        # so 5 labels implies quintiles, for example.
        num_categories = len(labels)
        breaks = np.linspace(0, 1, num_categories+1)
    
        # Compute the percentile values at each explicit data point in a.
        cu_weights = np.cumsum(tmp_weights)
        p_vals = (1.0/cu_weights[-1])*(cu_weights - 0.5*tmp_weights)
    
        # Set up the output array.
        ret = np.repeat(0, len(a))
        if(len(a)<num_categories):
            return ret
    
        # Set up the array for the values at the breakpoints.
        quantiles = []
    
    
        # Find the two indices that bracket the breakpoint percentiles.
        # then do interpolation on the two a_vals for those indices, using
        # interp-weights that involve the cumulative sum of weights.
        for brk in breaks:
            if brk <= p_vals[0]: 
                i_low = 0; i_high = 0;
            elif brk >= p_vals[-1]:
                i_low = N-1; i_high = N-1;
            else:
                for ii in range(N-1):
                    if (p_vals[ii] <= brk) and (brk < p_vals[ii+1]):
                        i_low  = ii
                        i_high = ii + 1       
    
            if i_low == i_high:
                v = tmp_a[i_low]
            else:
                # If there are two brackets, then apply the formula as per Wikipedia.
                v = tmp_a[i_low] + ((brk-p_vals[i_low])/(p_vals[i_high]-p_vals[i_low]))*(tmp_a[i_high]-tmp_a[i_low])
    
            # Append the result.
            quantiles.append(v)
    
        # Now that the weighted breakpoints are set, just categorize
        # the elements of a with logical indexing.
        for i in range(0, len(quantiles)-1):
            lower = quantiles[i]
            upper = quantiles[i+1]
            ret[ np.logical_and(a>=lower, a<upper) ] = labels[i] 
    
        #make sure upper and lower indices are marked
        ret[a<=quantiles[0]] = labels[0]
        ret[a>=quantiles[-1]] = labels[-1]
    
        return ret
    
    # The stats.stackexchange suggestion.
    elif method == 2:
    
        N = len(a)
        sort_indx = np.argsort(a)
        tmp_a = a[sort_indx].copy()
        tmp_weights = weights[sort_indx].copy()
    
    
        num_categories = len(labels)
        breaks = np.linspace(0, 1, num_categories+1)
    
        cu_weights = np.cumsum(tmp_weights)
    
        # Formula from stats.stackexchange.com post.
        s_vals = [0.0];
        for ii in range(1,N):
            s_vals.append( ii*tmp_weights[ii] + (N-1)*cu_weights[ii-1])
        s_vals = np.asarray(s_vals)
    
        # Normalized s_vals for comapring with the breakpoint.
        norm_s_vals = (1.0/s_vals[-1])*s_vals 
    
        # Set up the output variable.
        ret = np.repeat(0, N)
        if(N < num_categories):
            return ret
    
        # Set up space for the values at the breakpoints.
        quantiles = []
    
    
        # Find the two indices that bracket the breakpoint percentiles.
        # then do interpolation on the two a_vals for those indices, using
        # interp-weights that involve the cumulative sum of weights.
        for brk in breaks:
            if brk <= norm_s_vals[0]: 
                i_low = 0; i_high = 0;
            elif brk >= norm_s_vals[-1]:
                i_low = N-1; i_high = N-1;
            else:
                for ii in range(N-1):
                    if (norm_s_vals[ii] <= brk) and (brk < norm_s_vals[ii+1]):
                        i_low  = ii
                        i_high = ii + 1   
    
            if i_low == i_high:
                v = tmp_a[i_low]
            else:
                # Interpolate as in the method 1 method, but using the s_vals instead.
                v = tmp_a[i_low] + (( (brk*s_vals[-1])-s_vals[i_low])/(s_vals[i_high]-s_vals[i_low]))*(tmp_a[i_high]-tmp_a[i_low])
            quantiles.append(v)
    
        # Now that the weighted breakpoints are set, just categorize
        # the elements of a as usual. 
        for i in range(0, len(quantiles)-1):
            lower = quantiles[i]
            upper = quantiles[i+1]
            ret[ np.logical_and( a >= lower, a < upper ) ] = labels[i] 
    
        #make sure upper and lower indices are marked
        ret[a<=quantiles[0]] = labels[0]
        ret[a>=quantiles[-1]] = labels[-1]
    
        if return_quantiles:
            return ret, quantiles
        else:
            return ret
        

from numpy import cumsum, ones, sort, random       
from pandas import DataFrame

def gini(values, weights = None, bin_size = None):
    '''
    Gini coefficient (normalized to 1)
    Using fastgini formula :


                      i=N      j=i
                      SUM W_i*(SUM W_j*X_j - W_i*X_i/2)
                      i=1      j=1
          G = 1 - 2* ----------------------------------
                           i=N             i=N
                           SUM W_i*X_i  *  SUM W_i
                           i=1             i=1


        where observations are sorted in ascending order of X.
    
    From http://fmwww.bc.edu/RePec/bocode/f/fastgini.html
    '''
    if weights is None:
        weights = ones(len(values))
        
    df = DataFrame( {'x': values, 'w':weights} )    
    df = df.sort_index(by='x')
    x = df['x']
    w = df['w']
    wx = w*x
    
    cdf = cumsum(wx)-0.5*wx  
    numerator = (w*cdf).sum()
    denominator = ( (wx).sum() )*( w.sum() )
    gini = 1 - 2*( numerator/denominator) 
    
    return gini


def lorenz(values, weights = None):
    '''
    Computes Lorenz Curve coordinates
    '''
    if weights is None:
        weights = ones(len(values))
        
    df = DataFrame( {'v': values, 'w':weights} )    
    df = df.sort_index( by = 'v')    
    x = cumsum(df['w'])
    x = x/float(x[-1:])
    y = cumsum( df['v']*df['w'] )
    y = y/float(y[-1:])
    
    return x, y

from widgets.matplotlibwidget import MatplotlibWidget

def test():
    import sys
    from PyQt4.QtGui import QMainWindow, QApplication
    
    class ApplicationWindow(QMainWindow):
        def __init__(self):
            QMainWindow.__init__(self)
            self.mplwidget = MatplotlibWidget(self, title='Example',
                                              xlabel='x',
                                              ylabel='y',
                                              hold=True)
            self.mplwidget.setFocus()
            self.setCentralWidget(self.mplwidget)
            self.plot(self.mplwidget.axes)
            
        def plot(self, axes):
            x, y = lorenz(random.uniform(low=1,high=1.5,size=400))
            
            axes.plot(x,y)
            axes.plot(x,x)
        
    app = QApplication(sys.argv)
    win = ApplicationWindow()
    win.show()
    sys.exit(app.exec_())


if __name__=='__main__':

    test()

