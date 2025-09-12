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

import itertools
import re
from datetime import datetime

import six
import transaction
from bika.lims import api
from bika.lims import logger
from bika.lims.browser.fields.uidreferencefield import \
    get_backreferences as get_backuidreferences
from bika.lims.interfaces import IAnalysisRequest
from bika.lims.interfaces import IAnalysisRequestPartition
from bika.lims.interfaces import IAnalysisRequestRetest
from bika.lims.interfaces import IAnalysisRequestSecondary
from bika.lims.interfaces import IARReport
from DateTime import DateTime
from Products.ATContentTypes.utils import DT2dt
from senaite.core.idserver.alphanumber import Alphanumber
from senaite.core.idserver.alphanumber import to_alpha
from senaite.core.interfaces import IIdServer
from senaite.core.interfaces import IIdServerTypeID
from senaite.core.interfaces import IIdServerVariables
from senaite.core.interfaces import INumberGenerator
from zope.component import getAdapters
from zope.component import getUtility
from zope.component import queryAdapter

# 🔹 Import para detectar objetos temporales
from ZPublisher.BaseRequest import RequestContainer

AR_TYPES = [
    "AnalysisRequest",
    "AnalysisRequestRetest",
    "AnalysisRequestPartition",
    "AnalysisRequestSecondary",
]


def get_objects_in_sequence(brain_or_object, ctype, cref):
    obj = api.get_object(brain_or_object)
    if ctype == "backreference":
        return get_backreferences(obj, cref)
    if ctype == "contained":
        return get_contained_items(obj, cref)
    raise ValueError("Reference value is mandatory for sequence type counter")


def get_backreferences(obj, relationship):
    return get_backuidreferences(obj, relationship)


def get_contained_items(obj, spec):
    return obj.objectItems(spec)


def get_type_id(context, **kw):
    portal_type = kw.get("portal_type", None)
    if portal_type:
        return portal_type

    adapter = queryAdapter(context, IIdServerTypeID)
    if adapter:
        type_id = adapter.get_type_id(**kw)
        if type_id:
            return type_id

    if IAnalysisRequestPartition.providedBy(context):
        return "AnalysisRequestPartition"
    elif IAnalysisRequestRetest.providedBy(context):
        return "AnalysisRequestRetest"
    elif IAnalysisRequestSecondary.providedBy(context):
        return "AnalysisRequestSecondary"

    return api.get_portal_type(context)


def get_suffix(id, regex="-[A-Z]{1}[0-9]{1,2}$"):
    parts = re.findall(regex, id)
    if not parts:
        return ""
    return parts[0]


def strip_suffix(id):
    suffix = get_suffix(id)
    if not suffix:
        return id
    return re.split(suffix, id)[0]


def get_retest_count(context, default=0):
    if not is_ar(context):
        return default
    invalidated = context.getInvalidated()
    count = 0
    while invalidated:
        count += 1
        invalidated = invalidated.getInvalidated()
    return count


def get_partition_count(context, default=0):
    if not is_ar(context):
        return default
    parent = context.getParentAnalysisRequest()
    if not parent:
        return default
    return len(parent.getDescendants()) + 1


def get_secondary_count(context, default=0):
    if not is_ar(context):
        return default
    primary = context.getPrimaryAnalysisRequest()
    if not primary:
        return default
    return len(primary.getRawSecondaryAnalysisRequests())


def is_ar(context):
    return IAnalysisRequest.providedBy(context)


def get_config(context, **kw):
    """Fetch the config dict from the Bika Setup for the given portal_type"""
    config_map = api.get_bika_setup().getIDFormatting()
    portal_type = get_type_id(context, **kw)

    for config in config_map:
        if config['portal_type'].lower() == portal_type.lower():
            return config

    default_config = {
        'form': '%s-{seq}' % portal_type.lower(),
        'sequence_type': 'generated',
        'prefix': '%s' % portal_type.lower(),
    }

    # 🔹 Ajuste solo para AnalysisRequest → formato PREFIXyymmdd0000
    if portal_type.lower() == "analysisrequest":
        default_config = {
            'form': '{sampleType}{yymmdd}{seq:04d}',
            'sequence_type': 'generated',
            'prefix': 'AR',
        }

    return default_config


def get_variables(context, **kw):
    portal_type = get_type_id(context, **kw)
    parent = kw.get("container") or api.get_parent(context)

    # 🚨 Salida temprana si es un objeto temporal RequestContainer
    if isinstance(context, RequestContainer):
        return {
            "context": context,
            "id": None,
            "portal_type": portal_type,
            "year": get_current_year(),
            "yymmdd": get_yymmdd(),
            "parent": parent,
            "seq": 0,
            "alpha": Alphanumber(0),
            # Valores seguros
            "clientId": "",
            "dateSampled": DateTime(),
            "samplingDate": DateTime(),
            "sampleType": "TMP",
            "test_count": 0,
        }

    variables = {
        "context": context,
        "id": api.get_id(context),
        "portal_type": portal_type,
        "year": get_current_year(),
        "yymmdd": get_yymmdd(),
        "parent": parent,
        "seq": 0,
        "alpha": Alphanumber(0),
    }

    if IAnalysisRequest.providedBy(context):
        now = DateTime()
        sampling_date = context.getSamplingDate()
        sampling_date = sampling_date and DT2dt(sampling_date) or DT2dt(now)
        date_sampled = context.getDateSampled()
        date_sampled = date_sampled and DT2dt(date_sampled) or DT2dt(now)
        test_count = 1
        variables.update({
            "clientId": context.getClientID(),
            "dateSampled": date_sampled,
            "samplingDate": sampling_date,
            "sampleType": context.getSampleType().getPrefix(),
            "test_count": test_count
        })
        if IAnalysisRequestPartition.providedBy(context):
            parent_ar = context.getParentAnalysisRequest()
            parent_ar_id = api.get_id(parent_ar)
            parent_base_id = strip_suffix(parent_ar_id)
            partition_count = get_partition_count(context)
            variables.update({
                "parent_analysisrequest": parent_ar,
                "parent_ar_id": parent_ar_id,
                "parent_base_id": parent_base_id,
                "partition_count": partition_count,
            })
        elif IAnalysisRequestRetest.providedBy(context):
            parent_ar = context.getInvalidated()
            parent_ar_id = api.get_id(parent_ar)
            parent_base_id = strip_suffix(parent_ar_id)
            if context.isPartition():
                parent_base_id = parent_ar_id
            retest_count = get_retest_count(context)
            test_count = test_count + retest_count
            variables.update({
                "parent_analysisrequest": parent_ar,
                "parent_ar_id": parent_ar_id,
                "parent_base_id": parent_base_id,
                "retest_count": retest_count,
                "test_count": test_count,
            })
        elif IAnalysisRequestSecondary.providedBy(context):
            primary_ar = context.getPrimaryAnalysisRequest()
            primary_ar_id = api.get_id(primary_ar)
            parent_base_id = strip_suffix(primary_ar_id)
            secondary_count = get_secondary_count(context)
            variables.update({
                "parent_analysisrequest": primary_ar,
                "parent_ar_id": primary_ar_id,
                "parent_base_id": parent_base_id,
                "secondary_count": secondary_count,
            })

    elif IARReport.providedBy(context):
        variables.update({
            "clientId": parent.getClientID(),
        })

    adapter = queryAdapter(context, IIdServerVariables)
    if adapter:
        vars = adapter.get_variables(**kw)
        variables.update(vars)

    return variables


def split(string, separator="-"):
    if not isinstance(string, six.string_types):
        return []
    return string.split(separator)


def to_int(thing, default=0):
    try:
        return int(thing)
    except (TypeError, ValueError):
        return default


def slice(string, separator="-", start=None, end=None):
    segments = filter(None, re.split(r'(\{.+?})', string))
    if separator:
        segments = map(lambda seg: seg != separator and seg or "", segments)
        segments = map(lambda seg: split(seg, separator), segments)
        segments = list(itertools.chain.from_iterable(segments))
        segments = map(lambda seg: seg != "" and seg or separator, segments)
    cleaned_segments = filter(lambda seg: seg != separator, segments)
    start_pos = to_int(start, 0)
    end_pos = to_int(end, len(cleaned_segments) - start_pos) + start_pos - 1
    start = segments.index(cleaned_segments[start_pos])
    end = segments.index(cleaned_segments[end_pos]) + 1
    sliced_parts = segments[start:end]
    return "".join(sliced_parts)


def get_current_year():
    return DateTime().strftime("%Y")[2:]


def get_yymmdd():
    return datetime.now().strftime("%y%m%d")


def make_storage_key(portal_type, prefix=None):
    """🔹 Reinicio diario solo para AnalysisRequest"""
    if portal_type.lower() == "analysisrequest":
        today = datetime.now().strftime("%y%m%d")
        key = "{}-{}-{}".format(portal_type.lower(), prefix or "", today)
        return key

    key = portal_type.lower()
    if prefix:
        key = "{}-{}".format(key, prefix)
    return key


def get_seq_number_from_id(id, id_template, prefix, **kw):
    separator = kw.get("separator", "-")
    postfix = id.replace(prefix, "").strip(separator)
    postfix_segments = postfix.split(separator)
    seq_number = 0
    possible_seq_nums = filter(lambda n: n.isalnum(), postfix_segments)
    if possible_seq_nums:
        seq_number = possible_seq_nums[-1]
    seq_number = get_alpha_or_number(seq_number, id_template)
    seq_number = to_int(seq_number)
    return seq_number


def get_alpha_or_number(number, template):
    match = re.match(r".*\{alpha:(\d+a\d+d)\}$", template.strip())
    if match and match.groups():
        format = match.groups()[0]
        return to_alpha(number, format)
    return number


def get_counted_number(context, config, variables, **kw):
    ctx = config.get("context")
    obj = variables.get(ctx, context)
    counter_type = config.get("counter_type")
    if counter_type == "backreference":
        logger.warn("Counter type 'backreference' is obsolete!")
    counter_reference = config.get("counter_reference")
    seq_items = get_objects_in_sequence(obj, counter_type, counter_reference)
    number = len(seq_items)
    return number


def get_generated_number(context, config, variables, **kw):
    separator = kw.get('separator', '-')
    portal_type = get_type_id(context, **kw)
    id_template = config.get("form", "")
    split_length = config.get("split_length", 1)
    prefix_template = slice(id_template, separator=separator, end=split_length)
    number_generator = getUtility(INumberGenerator)
    prefix = prefix_template.format(**variables)
    prefix = api.normalize_filename(prefix)
    key = make_storage_key(portal_type, prefix)
    if not kw.get("dry_run", False):
        number = number_generator.generate_number(key=key)
    else:
        number = number_generator.get(key, 1)
    return get_alpha_or_number(number, id_template)


def generateUniqueId(context, **kw):
    config = get_config(context, **kw)
    variables = get_variables(context, **kw)
    number = 0
    sequence_type = config.get("sequence_type", "generated")
    if sequence_type in ["counter"]:
        number = get_counted_number(context, config, variables, **kw)
    if sequence_type in ["generated"]:
        number = get_generated_number(context, config, variables, **kw)
    if isinstance(number, Alphanumber):
        variables["alpha"] = number
    variables["seq"] = to_int(number)
    id_template = config.get("form", "")
    try:
        new_id = id_template.format(**variables)
    except KeyError as e:
        logger.error('KeyError: {} not in id_template {}'.format(e, id_template))
        raise
    normalized_id = api.normalize_filename(new_id)
    logger.info("generateUniqueId: {}".format(normalized_id))
    return normalized_id


def renameAfterCreation(obj):
    transaction.savepoint(optimistic=True)
    new_id = None
    for name, adapter in getAdapters((obj,), IIdServer):
        if new_id:
            logger.warn(('More than one ID Generator Adapter found for'
                         'content type -> %s') % obj.portal_type)
        new_id = adapter.generate_id(obj.portal_type)
    if not new_id:
        new_id = generateUniqueId(obj)
    parent = api.get_parent(obj)
    parent.manage_renameObject(obj.id, new_id)
    return new_id


