# -*- coding: utf-8 -*-
#
# This file is part of SENAITE.CORE.
#
# SENAITE.CORE is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the Free Software
# Foundation, version 2.
#
# SENAITE.CORE is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License
# for more details.
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


def _normalize_str(value):
    """Normaliza a texto plano (maneja dicts, strings, None)."""
    if isinstance(value, dict):
        for key in ("mrn", "MRN", "value", "text", "label", "title", "Title"):
            v = value.get(key)
            if isinstance(v, basestring) and v.strip():
                return v.strip()
        return u""
    if isinstance(value, basestring):
        return value.strip()
    return u""


def _get_ar(obj):
    """Devuelve el Analysis Request del análisis (o el propio obj si ya lo es)."""
    getter = getattr(obj, "getRequest", None)
    if callable(getter):
        try:
            ar = getter()
            if ar:
                return ar
        except Exception:
            pass
    return obj


def _get_mrn_from_ar(ar):
    """Lee MRN desde el campo 'MedicalRecordNumber' del AR (texto plano)."""
    if not hasattr(ar, "getField"):
        return u""
    field = ar.getField("MedicalRecordNumber")
    if not field:
        return u""
    try:
        raw = field.get(ar)
    except Exception:
        return u""
    return _normalize_str(raw)


def _get_patient_from_ar(ar):
    """Resuelve el paciente del AR o por MRN."""
    getp = getattr(ar, "getPatient", None)
    patient = None
    if callable(getp):
        try:
            patient = getp()
        except Exception:
            patient = None
    if patient:
        return patient

    mrn = _get_mrn_from_ar(ar)
    if not mrn:
        return None
    try:
        from senaite.patient.api import get_patient_by_mrn
        return get_patient_by_mrn(mrn)
    except Exception:
        return None


def _patient_fullname(patient):
    """Nombre completo robusto del paciente."""
    if not patient:
        return u""
    for key in ("getFullName", "getPatientFullName", "Title"):
        acc = getattr(patient, key, None)
        if callable(acc):
            try:
                return _safe_unicode(acc())
            except Exception:
                pass
        elif isinstance(acc, basestring):
            return _safe_unicode(acc)

    parts = []
    for fld in ("firstname", "middlename", "lastname", "maternal_lastname"):
        val = getattr(patient, fld, None)
        if val:
            parts.append(_safe_unicode(_normalize_str(val)))
    if parts:
        return u" ".join(parts)

    try:
        return _safe_unicode(patient.getId())
    except Exception:
        return u""


def _patient_mrn(patient):
    """Obtiene el MRN desde el paciente."""
    if not patient:
        return u""
    # getters
    for key in ("getMedicalRecordNumber", "getMRN"):
        acc = getattr(patient, key, None)
        if callable(acc):
            try:
                return _safe_unicode(acc())
            except Exception:
                pass
    # atributos directos
    v = getattr(patient, "mrn", None) or getattr(patient, "MedicalRecordNumber", None)
    return _safe_unicode(_normalize_str(v))


# -----------------------
# Indexers expuestos
# -----------------------

@indexer(IRequestAnalysis)
def getAncestorsUIDs(instance):
    """UID del AR y de sus ancestros."""
    request = instance.getRequest()
    parents = list(map(lambda ar: api.get_uid(ar), request.getAncestors()))
    return [api.get_uid(request)] + parents


@indexer(IRequestAnalysis)
def getPatientUID(obj):
    ar = _get_ar(obj)
    patient = _get_patient_from_ar(ar)
    try:
        return api.get_uid(patient) if patient else None
    except Exception:
        return None


@indexer(IRequestAnalysis)
def getPatientFullName(obj):
    ar = _get_ar(obj)
    patient = _get_patient_from_ar(ar)
    return _patient_fullname(patient) if patient else u""


@indexer(IRequestAnalysis)
def medical_record_number(obj):
    """Índice/metadata principal para MRN (coincide con el KeywordIndex del catálogo)."""
    ar = _get_ar(obj)

    # 1) Si hay paciente, prioriza su MRN
    patient = _get_patient_from_ar(ar)
    mrn = _patient_mrn(patient) if patient else u""
    if mrn:
        return mrn

    # 2) Fallback: MRN guardado en el AR
    return _safe_unicode(_get_mrn_from_ar(ar))


@indexer(IRequestAnalysis)
def is_temporary_mrn(obj):
    """BooleanIndex opcional para marcar MRN temporales."""
    ar = _get_ar(obj)
    acc = getattr(ar, "isMedicalRecordTemporary", None)
    if callable(acc):
        try:
            return bool(acc())
        except Exception:
            return False
    return False
