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

# -*- coding: utf-8 -*-
import re
import json
import string

import six
from bika.lims import api
from bika.lims import bikaMessageFactory as _
from bika.lims import logger
from Products.Archetypes.Registry import registerWidget
from senaite.core.browser.widgets.queryselect import QuerySelectWidget

# Universal: usamos Title, pero damos soporte a Fullname/MRN
IGNORE_COLUMNS = ["UID"]


class ReferenceWidget(QuerySelectWidget):
    """UID Reference Widget ajustado:
    - Mantiene Title como clave universal (colModel, ui_item, sidx).
    - Añade Fullname y MRN en get_render_data para usarlos en display_template.
    """
    klass = u"senaite-uidreference-widget-input"

    _properties = QuerySelectWidget._properties.copy()
    _properties.update({
        "value_key": "uid",
        "value_query_index": "UID",
        "url": "referencewidget_search",
        "catalog_name": None,
        "base_query": {},
        "colModel": [
            {"columnName": "Title", "width": "50", "label": _("Full name"), "align": "left"},
            {"columnName": "Description", "width": "50", "label": _("Description"), "align": "left"},
            {"columnName": "UID", "hidden": True},
        ],
        "ui_item": "Title",
        "search_fields": [],
        "discard_empty": [],
        "popup_width": "550px",
        "showOn": False,
        "searchIcon": True,
        "minLength": "0",
        "delay": "500",
        "resetButton": False,
        "sord": "asc",
        "sidx": "Title",
        "force_all": False,
        "portal_types": {},
    })

    def process_form(self, instance, field, form, empty_marker=None,
                     emptyReturnsMarker=False, validating=True):
        value = form.get(field.getName(), "")
        if api.is_string(value):
            uids = value.split("\r\n")
        elif isinstance(value, (list, tuple, set)):
            uids = filter(api.is_uid, value)
        elif api.is_object(value):
            uids = [api.get_uid(value)]
        else:
            uids = []
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
        prop = getattr(self, "display_template", None)
        if prop is not None:
            return prop
        # Universal → Title
        return "<a href='${url}' target='_blank'>${Title}</a>"

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
        # Fullname
        fullname = None
        try:
            if hasattr(obj, "getFullname"):
                fullname = obj.getFullname()
            elif hasattr(obj, "patient_fullname"):
                fullname = getattr(obj, "patient_fullname", None)
        except Exception as e:
            logger.warn("Could not build patient fullname: %s", e)
        if not fullname:
            fullname = api.get_title(obj)
        # MRN
        mrn = None
        for getter in ("getMRN", "getPatientID"):
            if hasattr(obj, getter):
                try:
                    mrn = getattr(obj, getter)()
                    break
                except Exception:
                    pass
        if mrn is None:
            mrn = getattr(obj, "mrn", None)
        data = {
            "uid": api.get_uid(obj),
            "url": api.get_url(obj),
            "Title": api.get_title(obj),  # universal
            "Fullname": fullname or api.get_title(obj),
            "mrn": mrn,
            "Description": api.get_description(obj),
        }
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

