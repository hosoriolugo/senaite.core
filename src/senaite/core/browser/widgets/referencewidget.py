# -*- coding: utf-8 -*-
#
# This file is part of SENAITE.CORE.
#
# SENAITE.CORE is free software: you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free
# Software Foundation, version 2.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc., 51
# Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
# Copyright 2018-2025 by it's authors.
# Some rights reserved, see README and LICENSE.

import re
import json
import string

import six
from bika.lims import api
from bika.lims import bikaMessageFactory as _
from bika.lims import logger
from Products.Archetypes.Registry import registerWidget
from senaite.core.browser.widgets.queryselect import QuerySelectWidget
from senaite.patient.api import _extract_fullname  # para normalizar nombre

DISPLAY_TEMPLATE = "<a href='${url}' _target='blank'>${Fullname}</a>"
IGNORE_COLUMNS = ["UID"]


class ReferenceWidget(QuerySelectWidget):
    """UID Reference Widget extendido con MRN y 4 campos de nombre
    """
    # CSS class that is picked up by the ReactJS component
    klass = u"senaite-uidreference-widget-input"

    _properties = QuerySelectWidget._properties.copy()
    _properties.update({

        "value_key": "uid",
        "value_query_index": "UID",

        # BBB: OLD PROPERTIES
        "url": "referencewidget_search",
        "catalog_name": None,
        # base_query can be a dict or a callable returning a dict
        "base_query": {},
        # columnas a mostrar en el popup de búsqueda
        "colModel": [
            {"columnName": "mrn", "width": "15", "label": _(u"MRN"), "align": "left"},
            {"columnName": "firstname", "width": "20", "label": _(u"Firstname"), "align": "left"},
            {"columnName": "middlename", "width": "20", "label": _(u"Middlename"), "align": "left"},
            {"columnName": "lastname", "width": "20", "label": _(u"Lastname"), "align": "left"},
            {"columnName": "maternal_lastname", "width": "20", "label": _(u"Second Lastname"), "align": "left"},
            {"columnName": "getLocalizedBirthdate", "width": "20", "label": _(u"Birthdate"), "align": "left"},
            {"columnName": "UID", "hidden": True},
        ],
        "ui_item": "Fullname",
        "search_fields": [],
        "discard_empty": [],
        "popup_width": "650px",
        "showOn": False,
        "searchIcon": True,
        "minLength": "0",
        "delay": "500",
        "resetButton": False,
        "sord": "asc",
        "sidx": "mrn",
        "force_all": False,
        "portal_types": {},
    })

    def process_form(self, instance, field, form, empty_marker=None,
                     emptyReturnsMarker=False, validating=True):
        """Convert the stored UIDs from the text field for the UID reference field
        """
        value = form.get(field.getName(), "")

        if api.is_string(value):
            uids = value.split("\r\n")
        elif isinstance(value, (list, tuple, set)):
            uids = filter(api.is_uid, value)
        elif api.is_object(value):
            uids = [api.get_uid(value)]
        else:
            uids = []

        # handle custom setters that expect only a UID, e.g. setSpecification
        multi_valued = getattr(field, "multiValued", self.multi_valued)
        if not multi_valued:
            uids = uids[0] if len(uids) > 0 else ""

        return uids, {}

    def get_multi_valued(self, context, field, default=None):
        multi_valued = getattr(field, "multiValued", None)
        if multi_valued is None:
            return default
        return multi_valued

    def get_display_template(self, context, field, default=None):
        # ahora usamos Fullname por defecto
        return DISPLAY_TEMPLATE

    def get_catalog(self, context, field, default=None):
        prop = getattr(self, "catalog", None)
        if prop is not None:
            return prop
        catalog_name = getattr(self, "catalog_name", None)
        if catalog_name is None:
            catalogs = api.get_catalogs_for(context)
            catalog_name = catalogs[0].getId()
        return catalog_name

    def get_query(self, context, field, default=None):
        base_query = self.get_base_query(context, field)
        query = getattr(self, "query", None)
        if isinstance(query, dict):
            base_query.update(query)
        allowed_types = getattr(field, "allowed_types", None)
        allowed_types_method = getattr(field, "allowed_types_method", None)
        if allowed_types_method:
            meth = getattr(context, allowed_types_method)
            allowed_types = meth(field)
        if api.is_string(allowed_types):
            allowed_types = [allowed_types]
        base_query["portal_type"] = list(allowed_types)
        return base_query

    def get_base_query(self, context, field):
        base_query = getattr(self, "base_query", {})
        if callable(base_query):
            try:
                base_query = base_query(context, self, field.getName())
            except TypeError:
                base_query = base_query()
        if api.is_string(base_query):
            base_query = json.loads(base_query)
        return base_query

    def get_columns(self, context, field, default=None):
        prop = getattr(self, "columns", [])
        if len(prop) > 0:
            return prop
        col_model = getattr(self, "colModel", [])
        if not col_model:
            return default
        columns = []
        for col in col_model:
            name = col.get("columnName")
            if name in IGNORE_COLUMNS:
                continue
            columns.append({
                "name": name,
                "width": col.get("width", "50%"),
                "align": col.get("align", "left"),
                "label": col.get("label", ""),
            })
        return columns

    def get_search_index(self, context, field, default=None):
        prop = getattr(self, "search_index", None)
        if prop is not None:
            return prop
        search_fields = getattr(self, "search_fields", [])
        if not isinstance(search_fields, (tuple, list)):
            search_fields = filter(None, [search_fields])
        if len(search_fields) > 0:
            return search_fields[0]
        return default

    def get_value(self, context, field, value=None):
        if isinstance(value, six.string_types):
            value = filter(None, value.split("\r\n"))
        if value is None:
            return []
        if not isinstance(value, (list, tuple)):
            value = [value]
        return map(api.get_uid, value)

    def get_render_data(self, context, field, uid, template):
        regex = r"\{(.*?)\}"
        names = re.findall(regex, template)

        try:
            obj = api.get_object(uid)
        except api.APIError:
            logger.error("No object found for field '{}' with UID '{}'".format(
                field.getName(), uid))
            return {}

        data = {
            "uid": api.get_uid(obj),
            "url": api.get_url(obj),
            "mrn": getattr(obj, "getMRN", lambda: u"")(),
            "firstname": getattr(obj, "getFirstname", lambda: u"")(),
            "middlename": getattr(obj, "getMiddlename", lambda: u"")(),
            "lastname": getattr(obj, "getLastname", lambda: u"")(),
            "maternal_lastname": getattr(obj, "getMaternalLastname", lambda: u"")(),
            "getLocalizedBirthdate": getattr(obj, "getLocalizedBirthdate", lambda: u"")(),
            "Title": api.get_title(obj),
            "Description": api.get_description(obj),
        }

        # construir Fullname normalizado
        data["Fullname"] = _extract_fullname(data)

        for name in names:
            if name not in data:
                value = getattr(obj, name, None)
                if callable(value):
                    value = value()
                data[name] = value

        return data

    def render_reference(self, context, field, uid):
        display_template = self.get_display_template(context, field, uid)
        template = string.Template(display_template)
        try:
            data = self.get_render_data(context, field, uid, display_template)
        except ValueError as e:
            logger.error(e.message)
            return ""
        if not data:
            return ""
        return template.safe_substitute(data)


registerWidget(ReferenceWidget, title="Reference Widget")
