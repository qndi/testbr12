# -*- coding: utf-8 -*-
# Copyright 2018-Today datenpol gmbh (<http://www.datenpol.at>)
# License OPL-1 or later (https://www.odoo.com/documentation/user/12.0/legal/licenses/licenses.html#licenses).

import logging
from collections import defaultdict
from urllib.parse import urljoin

import requests

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from odoo.tools import config

_logger = logging.getLogger(__name__)


def get_ai_service_url():
    url = config.get('ai_service_url')
    if not url:
        raise ValidationError(_(u'Please define the "ai_service_url" variable in the Odoo config file.'))
    return url


def get_ai_service_identifier():
    url = config.get('ai_service_identifier')
    if not url:
        raise ValidationError(_(u'Please define the "ai_service_identifier" variable in the Odoo config file.'))
    return url


class Classifier(models.AbstractModel):
    _name = 'dp.classifier'
    _description = 'classifier'

    check_prediction = fields.Boolean('Check Prediction', default=True)

    @api.model
    def ml_get_training_data(self):
        """
        Get all records and prepare them for training;
        data is a list, where each element contains the subject and the description in a string
        :return: list of strings of all records
        """
        records = self.search([('check_prediction', '=', False)])
        data = defaultdict(list)

        for record in records:
            value = record.get_predict_value()
            predicted_data = record.get_predict_data()
            if value and predicted_data:
                data[value].append(predicted_data)
        return data

    @api.multi
    def set_predict_data(self, prediction):
        """
        This method is responsible for writing the prediction in the right field of the model.
        Method has to be implemented.
        :param prediction: prediction from the ai-service
        """
        raise NotImplementedError(_('This method needs to be implemented when this model is inherited.'))

    @api.multi
    def get_predict_data(self):
        """
        This method prepares gets the data from the record to predict or to train and returns it.
        Method has to be implemented.
        :return: data to predict or to train
        """
        raise NotImplementedError(_('This method needs to be implemented when this model is inherited.'))

    def ml_train(self):
        """
        This method is used for the re(training) of the ML model.
        """
        data = self.ml_get_training_data()
        model = self._name

        if not data:
            _logger.info('No data available to train!')
            return False

        url = get_ai_service_url()
        url = urljoin(url, 'train')

        identifier = get_ai_service_identifier()

        try:
            r = requests.post(url, json={'data': data, 'model': model, 'identifier': identifier})
            r.raise_for_status()
        except Exception as e:
            _logger.error(e)
            return False

        return True

    def ml_predict(self, text):
        """
        This method is used for the prediction of the category according to the trained model and the input text.
        :param text: input (string)
        :return: predicted category (string)
        """
        model = self._name

        url = get_ai_service_url()
        url = urljoin(url, 'predict')

        identifier = get_ai_service_identifier()

        res = None
        try:
            r = requests.post(url, json={'data': text, 'model': model, 'identifier': identifier})
            r.raise_for_status()
            res = r.json().get('result')
        except Exception as e:
            _logger.error(e)

        return res

    @api.multi
    def predict(self):
        """
        Creates a prediction for the given record.
        :return: True
        """
        for record in self:
            text = record.get_predict_data()
            if text is not None:
                prediction = record.ml_predict(text)
                if prediction is not None:
                    record.set_predict_data(prediction)
        return True


class MailClassifier(models.AbstractModel):
    _name = 'dp.mail_classifier'
    _description = 'Mail classifier'

    @api.model
    def create(self, vals):
        """
        When a record is created, the message is send to the ai-service to get an prediction and then sets the predicted
        tags.
        :param vals:
        :return:
        """
        return super().create(vals).with_context(ai_service_predict=True)

    @api.multi
    @api.returns('mail.message', lambda value: value.id)
    def message_post(self, **kwargs):
        res = super().message_post(**kwargs)
        if res.env.context.get('ai_service_predict'):
            self.predict()
        return res
