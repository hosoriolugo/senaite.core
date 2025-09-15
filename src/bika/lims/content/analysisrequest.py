# -*- coding: utf-8 -*-
#
# This file is part of SENAITE.CORE.
#
# SENAITE.CORE is free software: you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation, version 2.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE. See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc., 51
# Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
# Copyright 2018-2025 by it's authors.
# Some rights reserved, see README and LICENSE.

import base64
import functools
import re
from collections import defaultdict
from datetime import datetime
from decimal import Decimal

from AccessControl import ClassSecurityInfo
from bika.lims import api
from bika.lims import bikaMessageFactory as _
from bika.lims import deprecated
from bika.lims import logger
from bika.lims.api.security import check_permission
from bika.lims.browser.fields import ARAnalysesField
from bika.lims.browser.fields import DurationField
from bika.lims.browser.fields import EmailsField
from bika.lims.browser.fields import ResultsRangesField
from bika.lims.browser.fields import UIDReferenceField
from bika.lims.browser.fields.remarksfield import RemarksField
from bika.lims.browser.fields.uidreferencefield import get_backreferences
from bika.lims.browser.widgets import DateTimeWidget
from bika.lims.browser.widgets import DecimalWidget
from bika.lims.browser.widgets import PrioritySelectionWidget
from bika.lims.browser.widgets import RejectionWidget
from bika.lims.browser.widgets import RemarksWidget
from bika.lims.browser.widgets import SelectionWidget as BikaSelectionWidget
from bika.lims.browser.widgets.durationwidget import DurationWidget
from bika.lims.config import PRIORITIES
from bika.lims.config import PROJECTNAME
from bika.lims.content.bikaschema import BikaSchema
from bika.lims.content.clientawaremixin import ClientAwareMixin
from bika.lims.interfaces import IAnalysisRequest
from bika.lims.interfaces import IAnalysisRequestPartition
from bika.lims.interfaces import IAnalysisRequestWithPartitions
from bika.lims.interfaces import IBatch
from bika.lims.interfaces import ICancellable
from bika.lims.interfaces import IClient
from bika.lims.interfaces import ISubmitted
from bika.lims.utils import getUsers
from bika.lims.utils import tmpID
from bika.lims.utils.analysisrequest import apply_hidden_services
from bika.lims.workflow import getTransitionDate
from bika.lims.workflow import getTransitionUsers
from DateTime import DateTime
from Products.Archetypes.atapi import BaseFolder
from Products.Archetypes.atapi import BooleanField
from Products.Archetypes.atapi import BooleanWidget
from Products.Archetypes.atapi import ComputedField
from Products.Archetypes.atapi import ComputedWidget
from Products.Archetypes.atapi import FileField
from Products.Archetypes.atapi import FileWidget
from Products.Archetypes.atapi import FixedPointField
from Products.Archetypes.atapi import StringField
from Products.Archetypes.atapi import StringWidget
from Products.Archetypes.atapi import TextField
from Products.Archetypes.atapi import registerType
from Products.Archetypes.config import UID_CATALOG
from Products.Archetypes.Field import IntegerField
from Products.Archetypes.public import Schema
from Products.Archetypes.Widget import IntegerWidget
from Products.Archetypes.Widget import RichWidget
from Products.CMFCore.permissions import ModifyPortalContent
from Products.CMFCore.permissions import View
from Products.CMFCore.utils import getToolByName
from Products.CMFPlone.utils import _createObjectByType
from Products.CMFPlone.utils import safe_unicode
from senaite.core.browser.fields.datetime import DateTimeField
from senaite.core.browser.fields.records import RecordsField
from senaite.core.browser.widgets.referencewidget import ReferenceWidget
from senaite.core.catalog import ANALYSIS_CATALOG
from senaite.core.catalog import CLIENT_CATALOG
from senaite.core.catalog import CONTACT_CATALOG
from senaite.core.catalog import SAMPLE_CATALOG
from senaite.core.catalog import SENAITE_CATALOG
from senaite.core.catalog import SETUP_CATALOG
from senaite.core.catalog import WORKSHEET_CATALOG
from senaite.core.permissions import FieldEditBatch
from senaite.core.permissions import FieldEditClient
from senaite.core.permissions import FieldEditClientOrderNumber
from senaite.core.permissions import FieldEditClientReference
from senaite.core.permissions import FieldEditClientSampleID
from senaite.core.permissions import FieldEditComposite
from senaite.core.permissions import FieldEditContact
from senaite.core.permissions import FieldEditContainer
from senaite.core.permissions import FieldEditDatePreserved
from senaite.core.permissions import FieldEditDateReceived
from senaite.core.permissions import FieldEditDateSampled
from senaite.core.permissions import FieldEditEnvironmentalConditions
from senaite.core.permissions import FieldEditInternalUse
from senaite.core.permissions import FieldEditInvoiceExclude
from senaite.core.permissions import FieldEditMemberDiscount
from senaite.core.permissions import FieldEditPreservation
from senaite.core.permissions import FieldEditPreserver
from senaite.core.permissions import FieldEditPriority
from senaite.core.permissions import FieldEditProfiles
from senaite.core.permissions import FieldEditPublicationSpecifications
from senaite.core.permissions import FieldEditRejectionReasons
from senaite.core.permissions import FieldEditRemarks
from senaite.core.permissions import FieldEditResultsInterpretation
from senaite.core.permissions import FieldEditSampleCondition
from senaite.core.permissions import FieldEditSamplePoint
from senaite.core.permissions import FieldEditSampler
from senaite.core.permissions import FieldEditSampleType
from senaite.core.permissions import FieldEditSamplingDate
from senaite.core.permissions import FieldEditSamplingDeviation
from senaite.core.permissions import FieldEditScheduledSampler
from senaite.core.permissions import FieldEditSpecification
from senaite.core.permissions import FieldEditStorageLocation
from senaite.core.permissions import FieldEditTemplate
from senaite.core.permissions import ManageInvoices
from six.moves.urllib.parse import urljoin
from zope.interface import alsoProvides
from zope.interface import implements
from zope.interface import noLongerProvides


IMG_SRC_RX = re.compile(r'<img.*?src="(.*?)"')
IMG_DATA_SRC_RX = re.compile(r'<img.*?src="(data:image/.*?;base64,)(.*?)"')
FINAL_STATES = ["published", "retracted", "rejected", "cancelled"]


# SCHEMA DEFINITION
schema = BikaSchema.copy() + Schema((

    UIDReferenceField(
        "Contact",
        required=1,
        allowed_types=("Contact",),
        mode="rw",
        read_permission=View,
        write_permission=FieldEditContact,
        widget=ReferenceWidget(
            label=_(
                "label_sample_contact",
                default="Contact"),
            description=_(
                "description_sample_contact",
                default="Select the primary contact for this sample"),
            render_own_label=True,
            visible={
                "add": "edit",
                "header_table": "prominent",
            },
            ui_item="Title",
            catalog=CONTACT_CATALOG,
            # TODO: Make custom query to handle parent client UID
            query={
                "getParentUID": "",
                "is_active": True,
                "sort_on": "sortable_title",
                "sort_order": "ascending"
            },
            columns=[
                {"name": "Title", "label": _("Name")},
                {"name": "getEmailAddress", "label": _("Email")},
            ],
        ),
    ),

    UIDReferenceField(
        "CCContact",
        multiValued=1,
        allowed_types=("Contact",),
        mode="rw",
        read_permission=View,
        write_permission=FieldEditContact,
        widget=ReferenceWidget(
            label=_(
                "label_sample_cccontact",
                default="CC Contact"),
            description=_(
                "description_sample_cccontact",
                default="The contacts used in CC for email notifications"),
            render_own_label=True,
            visible={
                "add": "edit",
                "header_table": "prominent",
            },
            ui_item="Title",
            catalog=CONTACT_CATALOG,
            # TODO: Make custom query to handle parent client UID
            query={
                "getParentUID": "",
                "is_active": True,
                "sort_on": "sortable_title",
                "sort_order": "ascending"
            },
            columns=[
                {"name": "Title", "label": _("Name")},
                {"name": "getEmailAddress", "label": _("Email")},
            ],
        ),
    ),

    EmailsField(
        'CCEmails',
        mode="rw",
        read_permission=View,
        write_permission=FieldEditContact,
        widget=StringWidget(
            label=_("CC Emails"),
            description=_("Additional email addresses to be notified"),
            visible={
                'add': 'edit',
                'header_table': 'prominent',
            },
            render_own_label=True,
            size=20,
        ),
    ),

    
    StringField(
        "patient_mrn",
        schemata="AR",
        required=0,
        widget=StringWidget(
            label=_("Patient MRN"),
            visible={"edit": "invisible", "view": "visible"},
        ),
    ),

    StringField(
        "patient_fullname",
        schemata="AR",
        required=0,
        widget=StringWidget(
            label=_("Patient Fullname"),
            visible={"edit": "invisible", "view": "visible"},
        ),
    ),
UIDReferenceField(
        "Client",
        required=1,
        allowed_types=("Client",),
        mode="rw",
        read_permission=View,
        write_permission=FieldEditClient,
        widget=ReferenceWidget(
            label=_(
                "label_sample_client",
                default="Client"),
            description=_(
                "description_sample_client",
                default="Select the client for this sample"),
            render_own_label=True,
            visible={
                "add": "edit",
                "header_table": "prominent",
            },
            ui_item="getName",
            catalog=CLIENT_CATALOG,
            search_index="client_searchable_text",
            query={
                "is_active": True,
                "sort_on": "sortable_title",
                "sort_order": "ascending"
            },
            columns=[
                {"name": "getName", "label": _("Name")},
                {"name": "getClientID", "label": _("Client ID")},
            ],
        ),
    ),

    # Field for the creation of Secondary Analysis Requests.
    # This field is meant to be displayed in AR Add form only. A viewlet exists
    # to inform the user this Analysis Request is secondary
    UIDReferenceField(
        "PrimaryAnalysisRequest",
        allowed_types=("AnalysisRequest",),
        relationship='AnalysisRequestPrimaryAnalysisRequest',
        mode="rw",
        read_permission=View,
        write_permission=FieldEditClient,
        widget=ReferenceWidget(
            label=_(
                "label_sample_primary",
                default="Primary Sample"),
            description=_(
                "description_sample_primary",
                default="Select a sample to create a secondary Sample"),
            render_own_label=True,
            visible={
                "add": "edit",
                "header_table": "prominent",
            },
            catalog_name=SAMPLE_CATALOG,
            search_index="listing_searchable_text",
            query={
                "is_active": True,
                "is_received": True,
                "sort_on": "sortable_title",
                "sort_order": "ascending"
            },
            columns=[
                {"name": "getId", "label": _("Sample ID")},
                {"name": "getClientSampleID", "label": _("Client SID")},
                {"name": "getSampleTypeTitle", "label": _("Sample Type")},
                {"name": "getClientTitle", "label": _("Client")},
            ],
            ui_item="getId",
        )
    ),

    UIDReferenceField(
        "Batch",
        allowed_types=("Batch",),
        mode="rw",
        read_permission=View,
        write_permission=FieldEditBatch,
        widget=ReferenceWidget(
            label=_(
                "label_sample_batch",
                default="Batch"),
            description=_(
                "description_sample_batch",
                default="Assign sample to a batch"),
            render_own_label=True,
            visible={
                "add": "edit",
            },
            catalog_name=SENAITE_CATALOG,
            search_index="listing_searchable_text",
            query={
                "is_active": True,
                "sort_on": "sortable_title",
                "sort_order": "ascending"
            },
            columns=[
                {"name": "getId", "label": _("Batch ID")},
                {"name": "Title", "label": _("Title")},
                {"name": "getClientBatchID", "label": _("CBID")},
                {"name": "getClientTitle", "label": _("Client")},
            ],
            ui_item="Title",
        )
    ),

    UIDReferenceField(
        "SubGroup",
        required=False,
        allowed_types=("SubGroup",),
        mode="rw",
        read_permission=View,
        write_permission=FieldEditBatch,
        widget=ReferenceWidget(
            label=_(
                "label_sample_subgroup",
                default="Batch Sub-group"),
            description=_(
                "description_sample_subgroup",
                default="The assigned batch sub group of this request"),
            render_own_label=True,
            visible={
                "add": "edit",
            },
            catalog_name=SETUP_CATALOG,
            query={
                "is_active": True,
                "sort_on": "sortable_title",
                "sort_order": "ascending"
            },
            ui_item="Title",
        )
    ),

    UIDReferenceField(
        "Template",
        allowed_types=("SampleTemplate",),
        mode="rw",
        read_permission=View,
        write_permission=FieldEditTemplate,
        widget=ReferenceWidget(
            label=_(
                "label_sample_template",
                default="Sample Template"),
            description=_(
                "description_sample_template",
                default="Select an analysis template for this sample"),
            render_own_label=True,
            visible={
                "add": "edit",
                "secondary": "disabled",
            },
            catalog=SETUP_CATALOG,
            query={
                "is_active": True,
                "sort_on": "sortable_title",
                "sort_order": "ascending"
            },
        ),
    ),

    UIDReferenceField(
        "Profiles",
        multiValued=1,
        allowed_types=("AnalysisProfile",),
        mode="rw",
        read_permission=View,
        write_permission=FieldEditProfiles,
        widget=ReferenceWidget(
            label=_(
                "label_sample_profiles",
                default="Analysis Profiles"),
            description=_(
                "description_sample_profiles",
                default="Select an analysis profile for this sample"),
            render_own_label=True,
            visible={
                "add": "edit",
            },
            catalog_name=SETUP_CATALOG,
            query="get_profiles_query",
            columns=[
                {"name": "Title", "label": _("Profile Name")},
                {"name": "getProfileKey", "label": _("Profile Key")},
            ],
        )
    ),

    # TODO Workflow - Request - Fix DateSampled inconsistencies...

DateTimeField(
    'DateSampled',
    mode="rw",
    max="getMaxDateSampled",
    read_permission=View,
    write_permission=FieldEditDateSampled,
    widget=DateTimeWidget(
        label=_(
            "label_sample_datesampled",
            default="Date Sampled"
        ),
        description=_(
            "description_sample_datesampled",
            default="The date when the sample was taken"
        ),
        size=20,
        show_time=True,
        visible={
            'add': 'edit',
            'secondary': 'disabled',
            'header_table': 'prominent',
        },
        render_own_label=True,
    ),
),

    StringField(
        'Sampler',
        mode="rw",
        read_permission=View,
        write_permission=FieldEditSampler,
        vocabulary='getSamplers',
        widget=BikaSelectionWidget(
            format='select',
            label=_("Sampler"),
            description=_("The person who took the sample"),
            visible={
                'add': 'edit',
                'header_table': 'prominent',
            },
            render_own_label=True,
        ),
    ),

    StringField(
        'ScheduledSamplingSampler',
        mode="rw",
        read_permission=View,
        write_permission=FieldEditScheduledSampler,
        vocabulary='getSamplers',
        widget=BikaSelectionWidget(
            description=_("Define the sampler supposed to do the sample in "
                          "the scheduled date"),
            format='select',
            label=_("Sampler for scheduled sampling"),
            visible={
                'add': 'edit',
            },
            render_own_label=True,
        ),
    ),

    UIDReferenceField(
        "SampleType",
        required=1,
        allowed_types=("SampleType",),
        mode="rw",
        read_permission=View,
        write_permission=FieldEditSampleType,
        widget=ReferenceWidget(
            label=_(
                "label_sample_sampletype",
                default="Sample Type"),
            description=_(
                "description_sample_sampletype",
                default="Select the sample type of this sample"),
            render_own_label=True,
            visible={
                "add": "edit",
                "secondary": "disabled",
            },
            catalog=SETUP_CATALOG,
            query={
                "is_active": True,
                "sort_on": "sortable_title",
                "sort_order": "ascending"
            },
        ),
    ),

    UIDReferenceField(
        "Container",
        required=0,
        allowed_types=("SampleContainer",),
        mode="rw",
        read_permission=View,
        write_permission=FieldEditContainer,
        widget=ReferenceWidget(
            label=_(
                "label_sample_container",
                default="Container"),
            description=_(
                "description_sample_container",
                default="Select a container for this sample"),
            render_own_label=True,
            visible={
                "add": "edit",
            },
            catalog_name=SETUP_CATALOG,
            query={
                "is_active": True,
                "sort_on": "sortable_title",
                "sort_order": "ascending"
            },
            columns=[
                {"name": "Title", "label": _("Container")},
                {"name": "getCapacity", "label": _("Capacity")},
            ],
        )
    ),

    UIDReferenceField(
        "Preservation",
        required=0,
        allowed_types=("SamplePreservation",),
        mode="rw",
        read_permission=View,
        write_permission=FieldEditPreservation,
        widget=ReferenceWidget(
            label=_(
                "label_sample_preservation",
                default="Preservation"),
            description=_(
                "description_sample_preservation",
                default="Select the needed preservation for this sample"),
            render_own_label=True,
            visible={
                "add": "edit",
            },
            catalog_name=SETUP_CATALOG,
            query={
                "is_active": True,
                "sort_on": "sortable_title",
                "sort_order": "ascending"
            },
        )
    ),

    DateTimeField(
        "DatePreserved",
        mode="rw",
        read_permission=View,
        write_permission=FieldEditDatePreserved,
        widget=DateTimeWidget(
            label=_("Date Preserved"),
            description=_("The date when the sample was preserved"),
            size=20,
            show_time=True,
            render_own_label=True,
            visible={
                'add': 'edit',
                'header_table': 'prominent',
            },
        ),
    ),

    StringField(
        "Preserver",
        required=0,
        mode="rw",
        read_permission=View,
        write_permission=FieldEditPreserver,
        vocabulary='getPreservers',
        widget=BikaSelectionWidget(
            format='select',
            label=_("Preserver"),
            description=_("The person who preserved the sample"),
            visible={
                'add': 'edit',
                'header_table': 'prominent',
            },
            render_own_label=True,
        ),
    ),

    DurationField(
        "RetentionPeriod",
        required=0,
        mode="r",
        read_permission=View,
        widget=DurationWidget(
            label=_("Retention Period"),
            visible=False,
        ),
    ),

    RecordsField(
        'RejectionReasons',
        mode="rw",
        read_permission=View,
        write_permission=FieldEditRejectionReasons,
        widget=RejectionWidget(
            label=_("Sample Rejection"),
            description=_("Set the Sample Rejection workflow and the reasons"),
            render_own_label=False,
            visible={
                'add': 'edit',
                'secondary': 'disabled',
            },
        ),
    ),

    UIDReferenceField(
        "Specification",
        required=0,
        primary_bound=True,
        allowed_types=("AnalysisSpec",),
        mode="rw",
        read_permission=View,
        write_permission=FieldEditSpecification,
        widget=ReferenceWidget(
            label=_(
                "label_sample_specification",
                default="Analysis Specification"),
            description=_(
                "description_sample_specification",
                default="Select an analysis specification for this sample"),
            render_own_label=True,
            visible={
                "add": "edit",
            },
            catalog_name=SETUP_CATALOG,
            query={
                "is_active": True,
                "sort_on": "sortable_title",
                "sort_order": "ascending"
            },
            columns=[
                {"name": "Title", "label": _("Specification Name")},
                {"name": "getSampleTypeTitle", "label": _("Sample Type")},
            ],
        )
    ),

    ResultsRangesField(
        "ResultsRange",
        write_permission=FieldEditSpecification,
        widget=ComputedWidget(visible=False),
    ),

    UIDReferenceField(
        "PublicationSpecification",
        required=0,
        allowed_types=("AnalysisSpec",),
        mode="rw",
        read_permission=View,
        write_permission=FieldEditPublicationSpecifications,
        widget=ReferenceWidget(
            label=_(
                "label_sample_publicationspecification",
                default="Publication Specification"),
            description=_(
                "description_sample_publicationspecification",
                default="Select an analysis specification that should be used "
                        "in the sample publication report"),
            render_own_label=True,
            visible={
                "add": "invisible",
                "secondary": "disabled",
            },
            catalog_name=SETUP_CATALOG,
            query={
                "is_active": True,
                "sort_on": "sortable_title",
                "sort_order": "ascending"
            },
            columns=[
                {"name": "Title", "label": _("Specification Name")},
                {"name": "getSampleTypeTitle", "label": _("Sample Type")},
            ],
        )
    ),

    UIDReferenceField(
        "SamplePoint",
        allowed_types=("SamplePoint",),
        mode="rw",
        read_permission=View,
        write_permission=FieldEditSamplePoint,
        widget=ReferenceWidget(
            label=_(
                "label_sample_samplepoint",
                default="Sample Point"),
            description=_(
                "description_sample_samplepoint",
                default="Location where the sample was taken"),
            render_own_label=True,
            visible={
                "add": "edit",
                "secondary": "disabled",
            },
            catalog_name=SETUP_CATALOG,
            query="get_sample_points_query",
        )
    ),

    UIDReferenceField(
        "StorageLocation",
        allowed_types=("StorageLocation",),
        mode="rw",
        read_permission=View,
        write_permission=FieldEditStorageLocation,
        widget=ReferenceWidget(
            label=_(
                "label_sample_storagelocation",
                default="Storage Location"),
            description=_(
                "description_sample_storagelocation",
                default="Location where the sample is kept"),
            render_own_label=True,
            visible={
                "add": "edit",
                "secondary": "disabled",
            },
            catalog_name=SETUP_CATALOG,
            query={
                "is_active": True,
                "sort_on": "sortable_title",
                "sort_order": "ascending"
            },
        )
    ),

    StringField(
        'ClientOrderNumber',
        mode="rw",
        read_permission=View,
        write_permission=FieldEditClientOrderNumber,
        widget=StringWidget(
            label=_("Client Order Number"),
            description=_("The client side order number for this request"),
            size=20,
            render_own_label=True,
            visible={
                'add': 'edit',
                'secondary': 'disabled',
            },
        ),
    ),

    StringField(
        'ClientReference',
        mode="rw",
        read_permission=View,
        write_permission=FieldEditClientReference,
        widget=StringWidget(
            label=_("Client Reference"),
            description=_("The client side reference for this request"),
            size=20,
            render_own_label=True,
            visible={
                'add': 'edit',
                'secondary': 'disabled',
            },
        ),
    ),

    StringField(
        'ClientSampleID',
        mode="rw",
        read_permission=View,
        write_permission=FieldEditClientSampleID,
        widget=StringWidget(
            label=_("Client Sample ID"),
            description=_("The client side identifier of the sample"),
            size=20,
            render_own_label=True,
            visible={
                'add': 'edit',
                'secondary': 'disabled',
            },
        ),
    ),

    UIDReferenceField(
        "SamplingDeviation",
        allowed_types=("SamplingDeviation",),
        mode="rw",
        read_permission=View,
        write_permission=FieldEditSamplingDeviation,
        widget=ReferenceWidget(
            label=_(
                "label_sample_samplingdeviation",
                default="Sampling Deviation"),
            description=_(
                "description_sample_samplingdeviation",
                default="Deviation between the sample and how it "
                        "was sampled"),
            render_own_label=True,
            visible={
                "add": "edit",
                "secondary": "disabled",
            },
            catalog_name=SETUP_CATALOG,
            query={
                "is_active": True,
                "sort_on": "sortable_title",
                "sort_order": "ascending"
            },
        )
    ),

    UIDReferenceField(
        "SampleCondition",
        allowed_types=("SampleCondition",),
        mode="rw",
        read_permission=View,
        write_permission=FieldEditSampleCondition,
        widget=ReferenceWidget(
            label=_(
                "label_sample_samplecondition",
                default="Sample Condition"),
            description=_(
                "description_sample_samplecondition",
                default="The condition of the sample"),
            render_own_label=True,
            visible={
                "add": "edit",
                "secondary": "disabled",
            },
            catalog_name=SETUP_CATALOG,
            query={
                "is_active": True,
                "sort_on": "sortable_title",
                "sort_order": "ascending"
            },
        )
    ),

    StringField(
        'Priority',
        default='3',
        vocabulary=PRIORITIES,
        mode='rw',
        read_permission=View,
        write_permission=FieldEditPriority,
        widget=PrioritySelectionWidget(
            label=_('Priority'),
            format='select',
            visible={
                'add': 'edit',
            },
        ),
    ),

    StringField(
        'EnvironmentalConditions',
        mode="rw",
        read_permission=View,
        write_permission=FieldEditEnvironmentalConditions,
        widget=StringWidget(
            label=_("Environmental conditions"),
            description=_("The environmental condition during sampling"),
            visible={
                'add': 'edit',
                'header_table': 'prominent',
            },
            render_own_label=True,
            size=20,
        ),
    ),

    BooleanField(
        'Composite',
        default=False,
        mode="rw",
        read_permission=View,
        write_permission=FieldEditComposite,
        widget=BooleanWidget(
            label=_("Composite"),
            render_own_label=True,
            visible={
                'add': 'edit',
                'secondary': 'disabled',
            },
        ),
    ),

    BooleanField(
        'InvoiceExclude',
        default=False,
        mode="rw",
        read_permission=View,
        write_permission=FieldEditInvoiceExclude,
        widget=BooleanWidget(
            label=_("Invoice Exclude"),
            description=_("Should the analyses be excluded from the invoice?"),
            render_own_label=True,
            visible={
                'add': 'edit',
                'header_table': 'visible',
            },
        ),
    ),

    ARAnalysesField(
        'Analyses',
        required=1,
        mode="rw",
        read_permission=View,
        write_permission=ModifyPortalContent,
        widget=ComputedWidget(
            visible={
                'edit': 'invisible',
                'view': 'invisible',
                'sample_registered': {
                    'view': 'visible', 'edit': 'visible', 'add': 'invisible'},
            }
        ),
    ),

    UIDReferenceField(
        'Attachment',
        multiValued=1,
        allowed_types=('Attachment',),
        relationship='AnalysisRequestAttachment',
        mode="rw",
        read_permission=View,
        write_permission=ModifyPortalContent,
        widget=ComputedWidget(
            visible={
                'edit': 'invisible',
                'view': 'invisible',
            },
        )
    ),

    FileField(
        '_ARAttachment',
        widget=FileWidget(
            label=_("Attachment"),
            description=_("Add one or more attachments to describe the "
                          "sample in this sample, or to specify "
                          "your request."),
            render_own_label=True,
            visible={
                'view': 'invisible',
                'add': 'edit',
                'header_table': 'invisible',
            },
        )
    ),

    UIDReferenceField(
        "Invoice",
        allowed_types=("Invoice",),
        mode="rw",
        read_permission=View,
        write_permission=ModifyPortalContent,
        widget=ReferenceWidget(
            label=_(
                "label_sample_invoice",
                default="Invoice"),
            description=_(
                "description_sample_invoice",
                default="Generated invoice for this sample"),
            render_own_label=True,
            readonly=True,
            visible={
                "add": "invisible",
                "view": "visible",
            },
            catalog_name=SENAITE_CATALOG,
            query={
                "is_active": True,
                "sort_on": "sortable_title",
                "sort_order": "ascending"
            },
        )
    ),

    DateTimeField(
        'DateReceived',
        mode="rw",
        min="DateSampled",
        max="current",
        read_permission=View,
        write_permission=FieldEditDateReceived,
        widget=DateTimeWidget(
            label=_("Date Sample Received"),
            show_time=True,
            description=_("The date when the sample was received"),
            render_own_label=True,
        ),
    ),

    ComputedField(
        'DatePublished',
        mode="r",
        read_permission=View,
        expression="here.getDatePublished().strftime('%Y-%m-%d %H:%M %p') if here.getDatePublished() else ''",
        widget=DateTimeWidget(
            label=_("Date Published"),
            visible={
                'edit': 'invisible',
                'add': 'invisible',
                'secondary': 'invisible',
            },
        ),
    ),

    RemarksField(
        'Remarks',
        read_permission=View,
        write_permission=FieldEditRemarks,
        widget=RemarksWidget(
            label=_("Remarks"),
            description=_("Remarks and comments for this request"),
            render_own_label=True,
            visible={
                'add': 'edit',
                'header_table': 'invisible',
            },
        ),
    ),

    FixedPointField(
        'MemberDiscount',
        default_method='getDefaultMemberDiscount',
        mode="rw",
        read_permission=View,
        write_permission=FieldEditMemberDiscount,
        widget=DecimalWidget(
            label=_("Member discount %"),
            description=_("Enter percentage value eg. 33.0"),
            render_own_label=True,
            visible={
                'add': 'invisible',
            },
        ),
    ),

    ComputedField(
        'SampleTypeTitle',
        expression="here.getSampleType().Title() if here.getSampleType() "
                   "else ''",
        widget=ComputedWidget(
            visible=False,
        ),
    ),

    ComputedField(
        'SamplePointTitle',
        expression="here.getSamplePoint().Title() if here.getSamplePoint() "
                   "else ''",
        widget=ComputedWidget(
            visible=False,
        ),
    ),

    ComputedField(
        'ContactUID',
        expression="here.getContact() and here.getContact().UID() or ''",
        widget=ComputedWidget(
            visible=False,
        ),
    ),

    ComputedField(
        'Invoiced',
        expression='here.getInvoice() and True or False',
        default=False,
        widget=ComputedWidget(
            visible=False,
        ),
    ),

    ComputedField(
        'ReceivedBy',
        expression='here.getReceivedBy()',
        default='',
        widget=ComputedWidget(visible=False,),
    ),

    ComputedField(
        'BatchID',
        expression="here.getBatch().getId() if here.getBatch() else ''",
        widget=ComputedWidget(visible=False),
    ),

    ComputedField(
        'BatchURL',
        expression="here.getBatch().absolute_url_path() "
                   "if here.getBatch() else ''",
        widget=ComputedWidget(visible=False),
    ),

    ComputedField(
        'ContactUsername',
        expression="here.getContact().getUsername() "
                   "if here.getContact() else ''",
        widget=ComputedWidget(visible=False),
    ),

    ComputedField(
        'ContactFullName',
        expression="here.getContact().getFullname() "
                   "if here.getContact() else ''",
        widget=ComputedWidget(visible=False),
    ),

    ComputedField(
        'ContactEmail',
        expression="here.getContact().getEmailAddress() "
                   "if here.getContact() else ''",
        widget=ComputedWidget(visible=False),
    ),

    ComputedField(
        'SampleTypeUID',
        expression="here.getSampleType().UID() "
                   "if here.getSampleType() else ''",
        widget=ComputedWidget(visible=False),
    ),

    ComputedField(
        'SamplePointUID',
        expression="here.getSamplePoint().UID() "
                   "if here.getSamplePoint() else ''",
        widget=ComputedWidget(visible=False),
    ),

    ComputedField(
        'StorageLocationUID',
        expression="here.getStorageLocation().UID() "
                   "if here.getStorageLocation() else ''",
        widget=ComputedWidget(visible=False),
    ),

    ComputedField(
        'TemplateUID',
        expression="here.getTemplate().UID() if here.getTemplate() else ''",
        widget=ComputedWidget(visible=False),
    ),

    ComputedField(
        'TemplateURL',
        expression="here.getTemplate().absolute_url_path() "
                   "if here.getTemplate() else ''",
        widget=ComputedWidget(visible=False),
    ),

    ComputedField(
        'TemplateTitle',
        expression="here.getTemplate().Title() if here.getTemplate() else ''",
        widget=ComputedWidget(visible=False),
    ),

    UIDReferenceField(
        "ParentAnalysisRequest",
        allowed_types=("AnalysisRequest",),
        relationship="AnalysisRequestParentAnalysisRequest",
        mode="rw",
        read_permission=View,
        write_permission=ModifyPortalContent,
        widget=ReferenceWidget(
            label=_(
                "label_sample_parent_sample",
                default="Parent sample"),
            description=_(
                "description_sample_parent_sample",
                default="Reference to parent sample"),
            render_own_label=True,
            readonly=True,
            visible=False,
            catalog_name=SAMPLE_CATALOG,
            query={
                "is_active": True,
                "sort_on": "sortable_title",
                "sort_order": "ascending"
            },
        )
    ),

    UIDReferenceField(
        "DetachedFrom",
        allowed_types=("AnalysisRequest",),
        mode="rw",
        read_permission=View,
        write_permission=ModifyPortalContent,
        widget=ReferenceWidget(
            label=_(
                "label_sample_detached_from",
                default="Detached from sample"),
            description=_(
                "description_sample_detached_from",
                default="Reference to detached sample"),
            render_own_label=True,
            readonly=True,
            visible=False,
            catalog_name=SAMPLE_CATALOG,
            query={
                "is_active": True,
                "sort_on": "sortable_title",
                "sort_order": "ascending"
            },
        )
    ),

    UIDReferenceField(
        "Invalidated",
        allowed_types=("AnalysisRequest",),
        relationship="AnalysisRequestRetracted",
        mode="rw",
        read_permission=View,
        write_permission=ModifyPortalContent,
        widget=ReferenceWidget(
            label=_(
                "label_sample_retracted",
                default="Retest from sample"),
            description=_(
                "description_sample_retracted",
                default="Reference to retracted sample"),
            render_own_label=True,
            readonly=True,
            visible=False,
            catalog_name=SAMPLE_CATALOG,
            query={
                "is_active": True,
                "sort_on": "sortable_title",
                "sort_order": "ascending"
            },
        )
    ),

    TextField(
        'ResultsInterpretation',
        mode="rw",
        default_content_type='text/html',
        default_output_type='text/x-html-safe',
        read_permission=View,
        write_permission=FieldEditResultsInterpretation,
        widget=RichWidget(
            description=_("Comments or results interpretation"),
            label=_("Results Interpretation"),
            size=10,
            allow_file_upload=False,
            default_mime_type='text/x-rst',
            output_mime_type='text/x-html',
            rows=3,
            visible=False),
    ),

    RecordsField(
        'ResultsInterpretationDepts',
        read_permission=View,
        write_permission=FieldEditResultsInterpretation,
        subfields=('uid', 'richtext'),
        subfield_labels={
            'uid': _('Department'),
            'richtext': _('Results Interpretation')},
        widget=RichWidget(visible=False),
     ),

    RecordsField('AnalysisServicesSettings',
                 required=0,
                 subfields=('uid', 'hidden',),
                 widget=ComputedWidget(visible=False),
                 ),

    StringField(
        'Printed',
        mode="rw",
        read_permission=View,
        widget=StringWidget(
            label=_("Printed"),
            description=_("Indicates if the last SampleReport is printed,"),
            visible=False,
        ),
    ),
    BooleanField(
        "InternalUse",
        mode="rw",
        required=0,
        default=False,
        read_permission=View,
        write_permission=FieldEditInternalUse,
        widget=BooleanWidget(
            label=_("Internal use"),
            description=_("Mark the sample for internal use only. This means "
                          "it is only accessible to lab personnel and not to "
                          "clients."),
            format="radio",
            render_own_label=True,
            visible={'add': 'edit'}
        ),
    ),

    RecordsField(
        "ServiceConditions",
        widget=ComputedWidget(visible=False)
    ),

    IntegerField(
        "NumSamples",
        default=1,
        widget=IntegerWidget(
            label=_(
                u"label_analysisrequest_numsamples",
                default=u"Number of samples"
            ),
            description=_(
                u"description_analysisrequest_numsamples",
                default=u"Number of samples to create with the information "
                        u"provided"),
            visible={
                "add": "edit",
                "view": "invisible",
                "header_table": "invisible",
                "secondary": "invisible",
            },
            render_own_label=True,
        ),
    ),
))

# Some schema rearrangement
schema['title'].required = False
schema['id'].widget.visible = False
schema['title'].widget.visible = False
schema.moveField('Client', before='Contact')
schema.moveField('ResultsInterpretation', pos='bottom')
schema.moveField('ResultsInterpretationDepts', pos='bottom')
schema.moveField("PrimaryAnalysisRequest", before="Client")


class AnalysisRequest(BaseFolder, ClientAwareMixin):
    implements(IAnalysisRequest, ICancellable)
    security = ClassSecurityInfo()
    displayContentsTab = False
    schema = schema

    def _getCatalogTool(self):
        from bika.lims.catalog import getCatalog
        return getCatalog(self)

    def Title(self):
        """ Return the Request ID as title """
        return self.getId()

    def sortable_title(self):
        """Some lists expects this index"""
        return self.getId()

    def Description(self):
        """Returns searchable data as Description"""
        descr = " ".join((self.getId(), self.aq_parent.Title()))
        return safe_unicode(descr).encode('utf-8')

    def setSpecification(self, value):
        """Sets the Specifications and ResultRange values"""
        current_spec = self.getRawSpecification()
        if value and current_spec == api.get_uid(value):
            return

        self.getField("Specification").set(self, value)

        spec = self.getSpecification()
        if spec:
            self.setResultsRange(spec.getResultsRange(), recursive=False)

        permission = self.getField("Specification").write_permission
        for descendant in self.getDescendants():
            if check_permission(permission, descendant):
                descendant.setSpecification(spec)

    def setResultsRange(self, value, recursive=True):
        """Sets the results range for this Sample and analyses it contains."""
        field = self.getField("ResultsRange")
        field.set(self, value)

        for analysis in self.objectValues("Analysis"):
            if not ISubmitted.providedBy(analysis):
                service_uid = analysis.getRawAnalysisService()
                result_range = field.get(self, search_by=service_uid)
                analysis.setResultsRange(result_range)
                analysis.reindexObject()

        if recursive:
            permission = self.getField("Specification").write_permission
            for descendant in self.getDescendants():
                if check_permission(permission, descendant):
                    descendant.setResultsRange(value)

    def setProfiles(self, value):
        """Set Analysis Profiles to the Sample"""
        if not isinstance(value, (list, tuple)):
            value = [value]
        value = filter(None, value)
        uids = map(api.get_uid, value)
        current_profiles = self.getRawProfiles()
        if current_profiles == uids:
            return

        if value and not api.is_temporary(self):
            profiles = map(api.get_object_by_uid, uids)
            analyses = self.getAnalyses(full_objects=True)
            services = map(lambda an: an.getAnalysisService(), analyses)
            services_to_add = set(services)
            for profile in profiles:
                services_to_add.update(profile.getServices())
            self.setAnalyses(list(services_to_add))

        self.getField("Profiles").set(self, value)
        apply_hidden_services(self)

    def getClient(self):
        """Returns the client this object is bound to."""
        parent = self.aq_parent
        if IClient.providedBy(parent):
            return parent
        elif IBatch.providedBy(parent):
            return parent.getClient()
        field = self.getField("Client")
        return field.get(self)

    @deprecated("Will be removed in SENAITE 3.0")
    def getProfilesURL(self):
        return [profile.absolute_url_path() for profile in self.getProfiles()]

    @deprecated("Please use getRawProfiles instead. Will be removed in SENAITE 3.0")
    def getProfilesUID(self):
        return self.getRawProfiles()

    def getProfilesTitle(self):
        return [profile.Title() for profile in self.getProfiles()]

    def getProfilesTitleStr(self, separator=", "):
        return separator.join(self.getProfilesTitle())

    def getAnalysisService(self):
        proxies = self.getAnalyses(full_objects=False)
        value = set()
        for proxy in proxies:
            value.add(proxy.Title)
        return list(value)

    def getAnalysts(self):
        proxies = self.getAnalyses(full_objects=True)
        value = []
        for proxy in proxies:
            val = proxy.getAnalyst()
            if val not in value:
                value.append(val)
        return value

    def getDistrict(self):
        client = self.aq_parent
        return client.getDistrict()

    def getProvince(self):
        client = self.aq_parent
        return client.getProvince()

    @security.public
    def getBatch(self):
        if self.aq_parent.portal_type == 'Batch':
            return self.aq_parent
        else:
            return self.Schema()['Batch'].get(self)

    @security.public
    def getBatchUID(self):
        batch = self.getBatch()
        if batch:
            return batch.UID()

    @security.public
    def setBatch(self, value=None):
        original_value = self.Schema().getField('Batch').get(self)
        if original_value != value:
            self.Schema().getField('Batch').set(self, value)

    def getDefaultMemberDiscount(self):
        """Compute default member discount if it applies"""
        if hasattr(self, 'getMemberDiscountApplies'):
            if self.getMemberDiscountApplies():
                settings = self.bika_setup
                return settings.getMemberDiscount()
            else:
                return "0.00"

    @security.public
    def getAnalysesNum(self):
        """[verified, total, not_submitted, to_be_verified]"""
        an_nums = [0, 0, 0, 0]
        for analysis in self.getAnalyses():
            review_state = analysis.review_state
            if review_state in ['retracted', 'rejected', 'cancelled']:
                continue
            if review_state == 'to_be_verified':
                an_nums[3] += 1
            elif review_state in ['published', 'verified']:
                an_nums[0] += 1
            else:
                an_nums[2] += 1
            an_nums[1] += 1
        return an_nums

    @security.public
    def getResponsible(self):
        """Return all manager info of responsible departments"""
        managers = {}
        for department in self.getDepartments():
            manager = department.getManager()
            if manager is None:
                continue
            manager_id = manager.getId()
            if manager_id not in managers:
                managers[manager_id] = {}
                managers[manager_id]['salutation'] = safe_unicode(
                    manager.getSalutation())
                managers[manager_id]['name'] = safe_unicode(
                    manager.getFullname())
                managers[manager_id]['email'] = safe_unicode(
                    manager.getEmailAddress())
                managers[manager_id]['phone'] = safe_unicode(
                    manager.getBusinessPhone())
                managers[manager_id]['job_title'] = safe_unicode(
                    manager.getJobTitle())
                if manager.getSignature():
                    managers[manager_id]['signature'] = \
                        '{}/Signature'.format(manager.absolute_url())
                else:
                    managers[manager_id]['signature'] = False
                managers[manager_id]['departments'] = ''
            mngr_dept = managers[manager_id]['departments']
            if mngr_dept:
                mngr_dept += ', '
            mngr_dept += safe_unicode(department.Title())
            managers[manager_id]['departments'] = mngr_dept
        mngr_keys = managers.keys()
        mngr_info = {'ids': mngr_keys, 'dict': managers}
        return mngr_info

    @security.public
    def getManagers(self):
        manager_ids = []
        manager_list = []
        for department in self.getDepartments():
            manager = department.getManager()
            if manager is None:
                continue
            manager_id = manager.getId()
            if manager_id not in manager_ids:
                manager_ids.append(manager_id)
                manager_list.append(manager)
        return manager_list

    def getDueDate(self):
        """Earliest due date of analyses"""
        due_dates = map(lambda an: an.getDueDate, self.getAnalyses())
        return due_dates and min(due_dates) or None

    security.declareProtected(View, 'getLate')

    def getLate(self):
        for analysis in self.getAnalyses():
            if analysis.review_state == "retracted":
                continue
            analysis_obj = api.get_object(analysis)
            if analysis_obj.isLateAnalysis():
                return True
        return False

    def getRawReports(self):
        """UIDs of reports referencing this sample"""
        return get_backreferences(self, "ARReportAnalysisRequest")

    def getReports(self):
        return list(map(api.get_object, self.getRawReports()))

    def getPrinted(self):
        """0/1/2 printed state"""
        if not self.getDatePublished():
            return "0"
        report_uids = self.getRawReports()
        if not report_uids:
            return "0"
        last_report = api.get_object(report_uids[-1])
        if last_report.getDatePrinted():
            return "1"
        for report_uid in report_uids[:-1]:
            report = api.get_object(report_uid)
            if report.getDatePrinted():
                return "2"
        return "0"

    @security.protected(View)
    def getBillableItems(self):
        """Items to be billed"""
        profiles = self.getProfiles()
        billable_profiles = filter(
            lambda pr: pr.getUseAnalysisProfilePrice(), profiles)
        billable_profile_services = functools.reduce(
            lambda a, b: a+b,
            map(lambda profile: profile.getServices(), billable_profiles),
            []
        )
        billable_service_keys = map(
            lambda s: s.getKeyword(), set(billable_profile_services))
        billable_items = billable_profiles
        exclude_rs = ["retracted", "rejected"]
        for analysis in self.getAnalyses(is_active=True):
            if analysis.review_state in exclude_rs:
                continue
            if analysis.getKeyword in billable_service_keys:
                continue
            billable_items.append(api.get_object(analysis))
        return billable_items

    @security.protected(View)
    def getSubtotal(self):
        return sum([Decimal(obj.getPrice()) for obj in self.getBillableItems()])

    @security.protected(View)
    def getSubtotalVATAmount(self):
        return sum([Decimal(o.getVATAmount()) for o in self.getBillableItems()])

    @security.protected(View)
    def getSubtotalTotalPrice(self):
        return self.getSubtotal() + self.getSubtotalVATAmount()

    @security.protected(View)
    def getDiscountAmount(self):
        has_client_discount = self.aq_parent.getMemberDiscountApplies()
        if has_client_discount:
            discount = Decimal(self.getDefaultMemberDiscount())
            return Decimal(self.getSubtotal() * discount / 100)
        else:
            return 0

    @security.protected(View)
    def getVATAmount(self):
        has_client_discount = self.aq_parent.getMemberDiscountApplies()
        VATAmount = self.getSubtotalVATAmount()
        if has_client_discount:
            discount = Decimal(self.getDefaultMemberDiscount())
            return Decimal((1 - discount / 100) * VATAmount)
        else:
            return VATAmount

    @security.protected(View)
    def getTotalPrice(self):
        price = (self.getSubtotal() - self.getDiscountAmount() +
                 self.getVATAmount())
        return price

    getTotal = getTotalPrice

    @security.protected(ManageInvoices)
    def createInvoice(self, pdf):
        client = self.getClient()
        invoice = self.getInvoice()
        if not invoice:
            invoice = _createObjectByType("Invoice", client, tmpID())
        invoice.edit(
            AnalysisRequest=self,
            Client=client,
            InvoiceDate=DateTime(),
            InvoicePDF=pdf
        )
        invoice.processForm()
        self.setInvoice(invoice)
        return invoice

    @security.public
    def printInvoice(self, REQUEST=None, RESPONSE=None):
        invoice = self.getInvoice()
        invoice_url = invoice.absolute_url()
        RESPONSE.redirect('{}/invoice_print'.format(invoice_url))

    @deprecated("Use getVerifiers instead. Will be removed in SENAITE 3.0")
    @security.public
    def getVerifier(self):
        wtool = getToolByName(self, 'portal_workflow')
        mtool = getToolByName(self, 'portal_membership')
        verifier = None
        try:
            review_history = wtool.getInfoFor(self, 'review_history')
        except Exception:
            return 'access denied'
        if not review_history:
            return 'no history'
        for items in review_history:
            action = items.get('action')
            if action != 'verify':
                continue
            actor = items.get('actor')
            member = mtool.getMemberById(actor)
            verifier = member.getProperty('fullname')
            if verifier is None or verifier == '':
                verifier = actor
        return verifier

    @security.public
    def getVerifiersIDs(self):
        verifiers_ids = list()
        for brain in self.getAnalyses():
            verifiers_ids += brain.getVerificators
        return list(set(verifiers_ids))

    @security.public
    def getVerifiers(self):
        contacts = list()
        for verifier in self.getVerifiersIDs():
            user = api.get_user(verifier)
            contact = api.get_user_contact(user, ["LabContact"])
            if contact:
                contacts.append(contact)
        return contacts

    def getWorksheets(self, full_objects=False):
        analyses_uids = map(api.get_uid, self.getAnalyses())
        if not analyses_uids:
            return []
        query = dict(getAnalysesUIDs=analyses_uids)
        worksheets = api.search(query, WORKSHEET_CATALOG)
        if full_objects:
            worksheets = map(api.get_object, worksheets)
        return worksheets

    def getQCAnalyses(self, review_state=None):
        worksheet_uids = map(api.get_uid, self.getWorksheets())
        if not worksheet_uids:
            return []
        query = dict(portal_type="ReferenceAnalysis",
                     getWorksheetUID=worksheet_uids)
        qc_analyses = api.search(query, ANALYSIS_CATALOG)
        query = dict(portal_type="DuplicateAnalysis",
                     getWorksheetUID=worksheet_uids,
                     getAncestorsUIDs=[api.get_uid(self)])
        qc_analyses += api.search(query, ANALYSIS_CATALOG)
        if review_state:
            qc_analyses = filter(
                lambda an: api.get_review_status(an) in review_state,
                qc_analyses
            )
        return map(api.get_object, qc_analyses)

    def isInvalid(self):
        workflow = getToolByName(self, 'portal_workflow')
        return workflow.getInfoFor(self, 'review_state') == 'invalid'

    def getStorageLocationTitle(self):
        sl = self.getStorageLocation()
        if sl:
            return sl.Title()
        return ''

    def getDatePublished(self):
        return getTransitionDate(self, 'publish', return_as_datetime=True)

    @security.public
    def getSamplingDeviationTitle(self):
        sd = self.getSamplingDeviation()
        if sd:
            return sd.Title()
        return ''

    @security.public
    def getSampleConditionTitle(self):
        obj = self.getSampleCondition()
        if not obj:
            return ""
        return api.get_title(obj)

    @security.public
    def getHazardous(self):
        sample_type = self.getSampleType()
        if sample_type:
            return sample_type.getHazardous()
        return False

    @security.public
    def getSamplingWorkflowEnabled(self):
        template = self.getTemplate()
        if template:
            return template.getSamplingRequired()
        return self.bika_setup.getSamplingWorkflowEnabled()

    def getSamplers(self):
        return getUsers(self, ['Sampler', ])

    def getPreservers(self):
        return getUsers(self, ['Preserver', 'Sampler'])

    def getDepartments(self):
        departments = list()
        for analysis in self.getAnalyses(full_objects=True):
            department = analysis.getDepartment()
            if department and not department in departments:
                departments.append(department)
        return departments

    def getResultsInterpretationByDepartment(self, department=None):
        uid = department.UID() if department else 'general'
        rows = self.Schema()['ResultsInterpretationDepts'].get(self)
        row = [row for row in rows if row.get('uid') == uid]
        if len(row) > 0:
            row = row[0]
        elif uid == 'general' \
                and hasattr(self, 'getResultsInterpretation') \
                and self.getResultsInterpretation():
            row = {'uid': uid, 'richtext': self.getResultsInterpretation()}
        else:
            row = {'uid': uid, 'richtext': ''}
        return row

    def getAnalysisServiceSettings(self, uid):
        sets = [s for s in self.getAnalysisServicesSettings()
                if s.get("uid", "") == uid]

        if not sets and self.getTemplate():
            adv = self.getTemplate().getAnalysisServiceSettings(uid)
            sets = [adv] if "hidden" in adv else []

        profiles = self.getProfiles()
        if not sets and profiles:
            adv = [profile.getAnalysisServiceSettings(uid) for profile in
                   profiles]
            sets = adv if adv[0].get("hidden") else []

        return sets[0] if sets else {"uid": uid}

    def getContainers(self):
        return self.getContainer() and [self.getContainer] or []

    def isAnalysisServiceHidden(self, uid):
        if not api.is_uid(uid):
            raise TypeError("Expected a UID, got '%s'" % type(uid))

        settings = self.getAnalysisServiceSettings(uid)

        if not settings or "hidden" not in settings.keys():
            serv = api.search({"UID": uid}, catalog="uid_catalog")
            if serv and len(serv) == 1:
                return serv[0].getObject().getRawHidden()
            else:
                raise ValueError("{} is not valid".format(uid))

        return settings.get("hidden", False)

    def getRejecter(self):
        wtool = getToolByName(self, 'portal_workflow')
        mtool = getToolByName(self, 'portal_membership')
        try:
            review_history = wtool.getInfoFor(self, 'review_history')
        except Exception:
            return None
        for items in review_history:
            action = items.get('action')
            if action != 'reject':
                continue
            actor = items.get('actor')
            return mtool.getMemberById(actor)
        return None

    def getReceivedBy(self):
        user = getTransitionUsers(self, 'receive', last_user=True)
        return user[0] if user else ''

    def getDateVerified(self):
        return getTransitionDate(self, 'verify', return_as_datetime=True)

    @security.public
    def getPrioritySortkey(self):
        priority = self.getPriority()
        created_date = self.created().ISO8601()
        return '%s.%s' % (priority, created_date)

    @security.public
    def setPriority(self, value):
        if not value:
            value = self.Schema().getField('Priority').getDefault(self)
        original_value = self.Schema().getField('Priority').get(self)
        if original_value != value:
            self.Schema().getField('Priority').set(self, value)
            self._reindexAnalyses(['getPrioritySortkey'], True)

    @security.private
    def _reindexAnalyses(self, idxs=None, update_metadata=False):
        if not idxs and not update_metadata:
            return
        if not idxs:
            idxs = []
        analyses = self.getAnalyses()
        catalog = getToolByName(self, ANALYSIS_CATALOG)
        for analysis in analyses:
            analysis_obj = analysis.getObject()
            catalog.reindexObject(analysis_obj, idxs=idxs, update_metadata=1)

    def getPriorityText(self):
        if self.getPriority():
            return PRIORITIES.getValue(self.getPriority())
        return ''

    def get_ARAttachment(self):
        return None

    def set_ARAttachment(self, value):
        return None

    def getRawRetest(self):
        relationship = self.getField("Invalidated").relationship
        uids = get_backreferences(self, relationship=relationship)
        return uids[0] if uids else None

    def getRetest(self):
        uid = self.getRawRetest()
        return api.get_object_by_uid(uid, default=None)

    def getAncestors(self, all_ancestors=True):
        parent = self.getParentAnalysisRequest()
        if not parent:
            return list()
        if not all_ancestors:
            return [parent]
        return [parent] + parent.getAncestors(all_ancestors=True)

    def isRootAncestor(self):
        parent = self.getParentAnalysisRequest()
        if parent:
            return False
        return True

    def getDescendants(self, all_descendants=False):
        uids = self.getDescendantsUIDs()
        if not uids:
            return []
        descendants = []
        cat = api.get_tool(UID_CATALOG)
        for brain in cat(UID=uids):
            descendant = api.get_object(brain)
            descendants.append(descendant)
            if all_descendants:
                descendants += descendant.getDescendants(all_descendants=True)
        return descendants

    def getDescendantsUIDs(self):
        relationship = self.getField("ParentAnalysisRequest").relationship
        return get_backreferences(self, relationship=relationship)

    def isPartition(self):
        return not self.isRootAncestor()

    def getSamplingRequired(self):
        return self.getSamplingWorkflowEnabled()

    def isOpen(self):
        for analysis in self.getAnalyses():
            if ISubmitted.providedBy(api.get_object(analysis)):
                return False
        return True

    def setParentAnalysisRequest(self, value):
        parent = self.getParentAnalysisRequest()
        self.Schema().getField("ParentAnalysisRequest").set(self, value)
        if not value:
            noLongerProvides(self, IAnalysisRequestPartition)
            if parent and not parent.getDescendants(all_descendants=False):
                noLongerProvides(self, IAnalysisRequestWithPartitions)
        else:
            alsoProvides(self, IAnalysisRequestPartition)
            parent = self.getParentAnalysisRequest()
            alsoProvides(parent, IAnalysisRequestWithPartitions)

    def getRawSecondaryAnalysisRequests(self):
        relationship = self.getField("PrimaryAnalysisRequest").relationship
        return get_backreferences(self, relationship)

    def getSecondaryAnalysisRequests(self):
        uids = self.getRawSecondaryAnalysisRequests()
        uc = api.get_tool("uid_catalog")
        return [api.get_object(brain) for brain in uc(UID=uids)]

    def setDateReceived(self, value):
        self.Schema().getField('DateReceived').set(self, value)
        for secondary in self.getSecondaryAnalysisRequests():
            secondary.setDateReceived(value)
            secondary.reindexObject(idxs=["getDateReceived", "is_received"])

    def setDateSampled(self, value):
        self.Schema().getField('DateSampled').set(self, value)
        for secondary in self.getSecondaryAnalysisRequests():
            secondary.setDateSampled(value)
            secondary.reindexObject(idxs="getDateSampled")

    def setSamplingDate(self, value):
        self.Schema().getField('SamplingDate').set(self, value)
        for secondary in self.getSecondaryAnalysisRequests():
            secondary.setSamplingDate(value)
            secondary.reindexObject(idxs="getSamplingDate")

    def getSelectedRejectionReasons(self):
        reasons = self.getRejectionReasons()
        if not reasons:
            return []
        reasons = reasons[0].get("selected", [])[:]
        return filter(None, reasons)

    def getOtherRejectionReasons(self):
        reasons = self.getRejectionReasons()
        if not reasons:
            return ""
        return reasons[0].get("other", "").strip()

    def createAttachment(self, filedata, filename="", **kw):
        attachment = api.create(self.getClient(), "Attachment")
        attachment.setAttachmentFile(filedata)
        fileobj = attachment.getAttachmentFile()
        fileobj.filename = filename
        attachment.edit(**kw)
        attachment.processForm()
        self.addAttachment(attachment)
        return attachment

    def addAttachment(self, attachment):
        if not isinstance(attachment, (list, tuple)):
            attachment = [attachment]
        original = self.getAttachment() or []
        original = map(api.get_uid, original)
        attachment = map(api.get_uid, attachment)
        attachment = filter(lambda at: at not in original, attachment)
        if attachment:
            original.extend(attachment)
            self.setAttachment(original)

    def setResultsInterpretationDepts(self, value):
        if not isinstance(value, list):
            raise TypeError("Expected list, got {}".format(type(value)))
        records = []
        for record in value:
            record = dict(record)
            html = record.get("richtext", "")
            record["richtext"] = self.process_inline_images(html)
            records.append(record)
        self.getField("ResultsInterpretationDepts").set(self, records)

    def process_inline_images(self, html):
        inline_images = re.findall(IMG_DATA_SRC_RX, html)
        for data_type, data in inline_images:
            filedata = base64.decodestring(data)
            extension = data_type.lstrip("data:image/").rstrip(";base64,")
            filename = "attachment.{}".format(extension or "png")
            attachment = self.createAttachment(filedata, filename)
            attachment.setRenderInReport(False)
            html = html.replace(data_type, "")
            html = html.replace(data, "resolve_attachment?uid={}".format(
                api.get_uid(attachment)))
            size = attachment.getAttachmentFile().get_size()
            logger.info("Converted {:.2f} Kb inline image for {}"
                        .format(size/1024, api.get_url(self)))

        image_sources = re.findall(IMG_SRC_RX, html)
        base_url = "{}/".format(api.get_url(self))
        for src in image_sources:
            if re.match("(http|https|data)", src):
                continue
            obj = self.restrictedTraverse(src, None)
            if obj is None:
                continue
            html = html.replace(src, urljoin(base_url, src))
        return html

    def getProgress(self):
        review_state = api.get_review_status(self)
        if review_state in FINAL_STATES:
            return 100
        numbers = self.getAnalysesNum()
        num_analyses = numbers[1] or 0
        if not num_analyses:
            return 0
        num_to_be_verified = numbers[3] or 0
        num_verified = numbers[0] or 0
        max_num_steps = (num_analyses * 2) + 1
        num_steps = num_to_be_verified + (num_verified * 2)
        if not num_steps:
            return 0
        if num_steps > max_num_steps:
            return 100
        return (num_steps * 100) / max_num_steps

    def getMaxDateSampled(self):
        if not self.getSamplingWorkflowEnabled():
            return api.get_creation_date(self)
        return datetime.max

    def get_profiles_query(self):
        sample_type_uid = self.getRawSampleType()
        query = {
            "portal_type": "AnalysisProfile",
            "sampletype_uid": [sample_type_uid, ""],
            "is_active": True,
            "sort_on": "title",
            "sort_order": "ascending",
        }
        return query

    def get_sample_points_query(self):
        sample_type_uid = self.getRawSampleType()
        query = {
            "portal_type": "SamplePoint",
            "sampletype_uid": [sample_type_uid, ""],
            "is_active": True,
            "sort_on": "sortable_title",
            "sort_order": "ascending",
        }
        return query


registerType(AnalysisRequest, PROJECTNAME)

