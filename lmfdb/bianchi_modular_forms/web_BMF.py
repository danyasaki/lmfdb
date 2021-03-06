# -*- coding: utf-8 -*-
from lmfdb.base import getDBConnection
from lmfdb.utils import make_logger
from lmfdb.WebNumberField import nf_display_knowl, field_pretty
from lmfdb.ecnf.WebEllipticCurve import FIELD
from lmfdb.elliptic_curves.web_ec import split_lmfdb_label
from lmfdb.modular_forms.elliptic_modular_forms.backend.emf_utils import newform_label, is_newform_in_db
from lmfdb.nfutils.psort import primes_iter, ideal_from_label, ideal_label
from lmfdb.utils import web_latex
from flask import url_for
from sage.all import QQ, PolynomialRing, NumberField

logger = make_logger("bmf")

def db_dims():
    return getDBConnection().bmfs.dimensions

def db_forms():
    return getDBConnection().bmfs.forms

def db_nf_fields():
    return getDBConnection().numberfields.fields

def db_ecnf():
    return getDBConnection().elliptic_curves.nfcurves

class WebBMF(object):
    """
    Class for an Bianchi Newform
    """
    def __init__(self, dbdata):
        """Arguments:

            - dbdata: the data from the database

        dbdata is expected to be a database entry from which the class
        is initialised.

        """
        logger.debug("Constructing an instance of WebBMF class from database")
        self.__dict__.update(dbdata)
        # All other fields are handled here
        self.make_form()

    @staticmethod
    def by_label(label):
        """
        Searches for a specific Hilbert newform in the forms
        collection by its label.
        """
        data = db_forms().find_one({"label" : label})

        if data:
            return WebBMF(data)
        raise ValueError("Bianchi newform %s not found" % label)
        # caller must catch this and raise an error


    def make_form(self):
        # To start with the data fields of self are just those from
        # the database.  We need to reformat these and compute some
        # further (easy) data about it.
        #
        self.field = FIELD(self.field_label)
        pretty_field = field_pretty(self.field_label)
        self.field_knowl = nf_display_knowl(self.field_label, getDBConnection(), pretty_field)
        try:
            dims = db_dims().find_one({'field_label':self.field_label, 'level_label':self.level_label})['gl2_dims']
            self.newspace_dimension = dims[str(self.weight)]['new_dim']
        except TypeError:
            self.newspace_dimension = 'not available'
        self.newspace_label = "-".join([self.field_label,self.level_label])
        self.newspace_url = url_for(".render_bmf_space_webpage", field_label=self.field_label, level_label=self.level_label)
        K = self.field.K()

        if self.dimension>1:
            Qx = PolynomialRing(QQ,'x')
            self.hecke_poly = Qx(str(self.hecke_poly))
            F = NumberField(self.hecke_poly,'z')
            self.hecke_poly = web_latex(self.hecke_poly)
            def conv(ap):
                if '?' in ap:
                    return 'not known'
                else:
                    return F(str(ap))
            self.hecke_eigs = [conv(str(ap)) for ap in self.hecke_eigs]

        self.nap = len(self.hecke_eigs)
        self.nap0 = min(50, self.nap)
        self.hecke_table = [[web_latex(p.norm()),
                             ideal_label(p),
                             web_latex(p.gens_reduced()[0]),
                             web_latex(ap)] for p,ap in zip(primes_iter(K), self.hecke_eigs[:self.nap0])]
        level = ideal_from_label(K,self.level_label)
        self.level_ideal2 = web_latex(level)
        badp = level.prime_factors()
        self.have_AL = self.AL_eigs[0]!='?'
        if self.have_AL:
            self.AL_table = [[web_latex(p.norm()),
                             ideal_label(p),
                              web_latex(p.gens_reduced()[0]),
                              web_latex(ap)] for p,ap in zip(badp, self.AL_eigs)]
        self.sign = 'not determined'
        if self.sfe == 1:
            self.sign = "+1"
        elif self.sfe == -1:
            self.sign = "-1"

        if self.Lratio == '?':
            self.Lratio = "not determined"
            self.anrank = "not determined"
        else:
            self.Lratio = QQ(self.Lratio)
            self.anrank = "\(0\)" if self.Lratio!=0 else "odd" if self.sfe==-1 else "\(\ge2\), even"

        self.properties2 = [('Base field', pretty_field),
                            ('Weight', str(self.weight)),
                            ('Level norm', str(self.level_norm)),
                            ('Level', self.level_ideal2),
                            ('Label', self.label),
                            ('Dimension', str(self.dimension))
        ]

        if self.CM == '?':
            self.CM = 'not determined'
        elif self.CM == 0:
            self.CM = 'no'
        self.properties2.append(('CM', str(self.CM)))

        self.bc_extra = ''
        self.bcd = 0
        self.bct = self.bc!='?' and self.bc!=0
        if self.bc == '?':
            self.bc = 'not determined'
        elif self.bc == 0:
            self.bc = 'no'
        elif self.bc == 1:
            self.bcd = self.bc
            self.bc = 'yes'
        elif self.bc >1:
            self.bcd = self.bc
            self.bc = 'yes'
            self.bc_extra = ', of a form over \(\mathbb{Q}\) with coefficients in \(\mathbb{Q}(\sqrt{'+str(self.bcd)+'})\)'
        elif self.bc == -1:
            self.bc = 'no'
            self.bc_extra = ', but is a twist of the base-change of a form over \(\mathbb{Q}\)'
        elif self.bc < -1:
            self.bcd = -self.bc
            self.bc = 'no'
            self.bc_extra = ', but is a twist of the base-change of a form over \(\mathbb{Q}\) with coefficients in \(\mathbb{Q}(\sqrt{'+str(self.bcd)+'})\)'
        self.properties2.append(('Base-change', str(self.bc)))

        curve = db_ecnf().find_one({'class_label':self.label})
        if curve:
            self.ec_status = 'exists'
            self.ec_url = url_for("ecnf.show_ecnf_isoclass", nf=self.field_label, conductor_label=self.level_label, class_label=self.label_suffix)
            curve_bc = curve['base_change']
            curve_bc_parts = [split_lmfdb_label(lab) for lab in curve_bc]
            bc_urls = [url_for("emf.render_elliptic_modular_forms", level=cond, weight=2, character=1, label=iso) for cond, iso, num in curve_bc_parts]
            bc_labels = [newform_label(cond,2,1,iso) for cond,iso,num in curve_bc_parts]
            bc_exists = [is_newform_in_db(lab) for lab in bc_labels]
            self.bc_forms = [{'exists':ex, 'label':lab, 'url':url} for ex,lab,url in zip(bc_exists, bc_labels, bc_urls)]
        else:
            self.bc_forms = []
            if self.bct:
                self.ec_status = 'none'
            else:
                self.ec_status = 'missing'

        self.properties2.append(('Sign', self.sign))
        self.properties2.append(('Analytic rank', self.anrank))

        self.friends = []
        if self.dimension==1:
            if self.ec_status == 'exists':
                self.friends += [('Elliptic curve isogeny class {}'.format(self.label), self.ec_url)]
            elif self.ec_status == 'missing':
                self.friends += [('Elliptic curve {} missing'.format(self.label), "")]
            else:
                self.friends += [('No elliptic curve', "")]

        self.friends += [ ('Newspace {}'.format(self.newspace_label),self.newspace_url)]
        self.friends += [ ('L-function not available','')]
