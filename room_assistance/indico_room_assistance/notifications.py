# This file is part of the CERN Indico plugins.
# Copyright (C) 2014 - 2019 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

from __future__ import unicode_literals

from flask_pluginengine import render_plugin_template

from indico.core.notifications import make_email, send_email
from indico.modules.rb import rb_settings
from indico.util.date_time import format_datetime
from indico.util.string import to_unicode


def _get_email_subject(reservation, mail_params):
    return u'{prefix}[{room}] {subject} {date} {suffix}'.format(
        prefix=to_unicode(mail_params.get('subject_prefix', '')),
        room=reservation.room.full_name,
        subject=to_unicode(mail_params.get('subject', '')),
        date=to_unicode(format_datetime(reservation.start_dt)),
        suffix=to_unicode(mail_params.get('subject_suffix', ''))
    ).strip()


def _make_body(mail_params, **body_params):
    from indico.modules.rb.models.reservations import RepeatFrequency, RepeatMapping
    template_params = dict(mail_params, **body_params)
    template_params['RepeatFrequency'] = RepeatFrequency
    template_params['RepeatMapping'] = RepeatMapping
    return render_plugin_template('emails/{}.txt'.format(mail_params['template_name']), **template_params)


def send_email_to_assistance(reservation=None, occurrence=None, **mail_params):
    reservation = reservation or occurrence.reservation
    if reservation.room_assistance_request is None:
        return

    to_list = rb_settings.get('assistance_emails')
    if to_list:
        subject = _get_email_subject(reservation, mail_params)
        body = _make_body(mail_params, reservation=reservation, occurrence=occurrence)
        send_email(make_email(to_list=to_list, subject=subject, body=body))


def notify_confirmation(reservation):
    if not reservation.is_accepted:
        return
    send_email_to_assistance(reservation=reservation, subject_prefix='[Support Request]', subject='New Support on',
                             template_name='creation_email_to_assistance')


def notify_creation(reservation):
    send_email_to_assistance(reservation=reservation, subject_prefix='[Support Request]', subject='New Booking on',
                             template_name='creation_email_to_assistance')


def notify_cancellation(reservation):
    if not reservation.is_cancelled:
        return
    send_email_to_assistance(reservation=reservation, subject_prefix='[Support Request Cancellation]',
                             subject='Request cancelled for', template_name='cancellation_email_to_assistance')


def notify_rejection(reservation):
    if not reservation.is_rejected:
        return
    send_email_to_assistance(reservation=reservation, subject_prefix='[Support Request Cancellation]',
                             subject='Request cancelled for', template_name='rejection_email_to_assistance')


def notify_modification(reservation, changes):
    assistance_change = changes.get('needs_assistance')
    assistance_cancelled = assistance_change and assistance_change['old'] and not assistance_change['new']
    subject_prefix = '[Support Request {}]'.format('Cancelled' if assistance_cancelled else 'Modification')
    send_email_to_assistance(reservation=reservation, subject_prefix=subject_prefix, subject='Modified request on',
                             template_name='modification_email_to_assistance',
                             assistance_cancelled=assistance_cancelled)


def notify_occurrence_cancellation(occurrence):
    if not occurrence.is_cancelled:
        return
    send_email_to_assistance(occurrence=occurrence, subject_prefix='[Support Request Cancellation]',
                             subject='Request cancelled for',
                             template_name='occurrence_cancellation_email_to_assistance')


def notify_occurrence_rejection(occurrence):
    if not occurrence.is_rejected:
        return
    send_email_to_assistance(occurrence=occurrence, subject_prefix='[Support Request Cancellation]',
                             subject='Request cancelled for',
                             template_name='occurrence_rejection_email_to_assistance')
