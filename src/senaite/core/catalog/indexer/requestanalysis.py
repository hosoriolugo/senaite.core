# -*- coding: utf-8 -*-
#
# This file is part of SENAITE.CORE.
#
# SENAITE.CORE is free software: you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation, version 2.
#
# SENAITE.CORE is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# General Public License for more details.
#
# ------------------------------------------------------------------------
# Adjusted: Robust indexers for MRN and Patient fields in ARs
# ------------------------------------------------------------------------

from __future__ import absolute_import

from bika.lims import api
from bika.lims.interfaces.analysis import IRequestAnalysis
from plone.indexer import indexer

try:
    basestring
except NameError:
    basestring = str


def _safe_unicode(value):
    try:
        return api.safe_unicode(value or u"")
    except Exception:
        try:
            return api.safe_unicode(u"%s" % value)
        except Exception:
            return u""


def _get_patient(obj):
    """Resolve patient from AR object or MRN fallback"""
    getter = getattr(obj, "getPatient", None)
    patient = None
    if callable(getter):
        try:
            patient = getter()
        except Exception:
            patient = None

    if not patient:
        # fallback by MRN
        for key in (
            "getMedicalRecordNumberValue",
            "MedicalRecordNumber",
            "getMedicalRecordNumber",
            "medical_record_number",
            "mrn",
        ):
            acc = getattr(obj, key, None)
            mrn = None
            if callable(acc):
                try:
                    mrn = acc()
                except Exception:
                    mrn = None
            elif isinstance(acc, basestring):
                mrn = acc
            if mrn:
                try:
                    from senaite.patient.api import get_patient_by_mrn
                    patient = get_patient_by_mrn(mrn)
                except Exception:
                    patient = None
                break
    return patient


def _patient_fullname(patient):
    """Build robust patient fullname"""
    if not patient:
        return u""

    # try standard fullname getters
    for key in ("getFullName", "getPatientFullName", "Title"):
        acc = getattr(patient, key, None)
        if callable(acc):
            try:
                return _safe_unicode(acc())
            except Exception:
                pass
        elif isinstance(acc, basestring):
            return _safe_unicode(acc)

    # build from 4 fields
    parts = []
    for fld in ("firstname", "middlename", "lastname", "maternal_lastname"):
        val = getattr(patient, fld, None)
        if val:
            parts.append(_safe_unicode(val))
    if parts:
        return u" ".join(parts)

    # fallback to id
    try:
        return _safe_unicode(patient.getId())
    except Exception:
        return u""


def _patient_mrn(patient):
    """Get MRN from patient"""
    if not patient:
        return u""
    # direct getters
    for key in ("getMedicalRecordNumber", "getMRN"):
        acc = getattr(patient, key, None)
        if callable(acc):
            try:
                return _safe_unicode(acc())
            except Exception:
                pass
    # attribute fallback (prioritize `mrn`)
    v = getattr(patient, "mrn", None) or getattr(patient, "MedicalRecordNumber", None)
    if isinstance(v, basestring):
        return _safe_unicode(v)
    return u""


@indexer(IRequestAnalysis)
def getAncestorsUIDs(instance):
    """Returns the UIDs of all the ancestors (Analysis Requests) this analysis comes from"""
    request = instance.getRequest()
    parents = map(lambda ar: api.get_uid(ar), request.getAncestors())
    return [api.get_uid(request)] + parents


@indexer(IRequestAnalysis)
def getPatientUID(obj):
    patient = _get_patient(obj)
    try:
        return api.get_uid(patient) if patient else None
    except Exception:
        return None


@indexer(IRequestAnalysis)
def getPatientFullName(obj):
    patient = _get_patient(obj)
    return _patient_fullname(patient) if patient else u""


@indexer(IRequestAnalysis)
def getMedicalRecordNumberValue(obj):
    patient = _get_patient(obj)
    if patient:
        mrn = _patient_mrn(patient)
        if mrn:
            return mrn
    # fallback to AR attributes
    for key in (
        "getMedicalRecordNumberValue",
        "MedicalRecordNumber",
        "getMedicalRecordNumber",
        "medical_record_number",
        "mrn",
    ):
        acc = getattr(obj, key, None)
        if callable(acc):
            try:
                return _safe_unicode(acc())
            except Exception:
                continue
        elif isinstance(acc, basestring):
            return _safe_unicode(acc)
    return u""
