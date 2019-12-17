# -*- coding: utf-8 -*-
# Copyright 2018-Today datenpol gmbh (<http://www.datenpol.at>)
# License OPL-1 or later (https://www.odoo.com/documentation/user/11.0/legal/licenses/licenses.html#licenses).

import logging
import requests
from odoo import fields, models
from odoo.tools import config
from odoo.exceptions import UserError

# Try, da ansonsten ein ImportError geworfen wird, wenn es das Modul nicht gibt
try:
    from elasticsearch import Elasticsearch
    from elasticsearch.client.ingest import IngestClient
    from elasticsearch.client import IndicesClient
except ImportError:
    Elasticsearch = None
    IngestClient = None

_logger = logging.getLogger(__name__)
escape_char = ["\\", "+", "-", "&&", "||", "!", "(", ")", "{", "}", "[", "]", "^", '"', "~", "*", "?", ":", "/"]

class ElasticIndex(models.AbstractModel):
    _name = 'elastic.index'
    _description = 'Elasticsearch Index'
    _elastic_index_attachments = True
    _elastic_index_message = True

    score = fields.Float(string='Score', help='Search Score', digits=(16, 2), default=0, store=False)
    elastic_filter = fields.Char(string='Dummy Field for Search View Filter', default=False, store=False)

    def elastic_fields(self):
        # Indexable Fields of Model. Needs to be overwritten.
        # :return: List of Fields['tag_ids','attachmend_ids']

        return []

    def index(self):
        try:
            self._index()
        except Exception as e:
            _logger.debug(e)
            pass

    def create(self, vals_list):
        res = super(ElasticIndex, self).create(vals_list)
        res.index()
        return res

    def write(self, vals):
        res = super(ElasticIndex, self).write(vals)
        if any(field in self.elastic_fields() for field in vals):
            self.index()
        return res

    def unlink(self):
        if self._get_host():
            self.env.context = dict(self.env.context, unlink_index=True)
            self.remove_index_record()
        return super(ElasticIndex, self).unlink()

    def remove_index_record(self):
        # delete document/record in index
        try:
            es = Elasticsearch(self._get_host())
            if es:
                for record in self:
                    es.delete(index=record._get_index_name(), doc_type='odoo_record', id=record.id, ignore=[400, 404])
        except Exception as e:
            _logger.debug(e)
            pass

    def remove_index(self):
        # delete whole index with all indexed documents
        try:
            es = Elasticsearch(self._get_host())
            es.indices.delete(index=self._get_index_name())
        except Exception as e:
            _logger.debug(e)
            pass

    def search_query(self, query):
        query_fields = [{
                "query_string": {
                    "fields": self.elastic_fields(),
                    "query": query,
                    "fuzziness": "AUTO",

                }
            }]
        if self._elastic_index_message:
            query_fields.append(
                {
                    "nested": {
                        "path": "messages",
                        "score_mode": "avg",
                        "query": {
                            "query_string": {
                                "fields": ["messages.subject", "messages.body"],
                                "query": query,
                                "fuzziness": "AUTO"
                            }
                        }
                    }
                }
            )
        if self._elastic_index_attachments:
            query_fields.append(
                {
                    "nested": {
                        "path": "attachments",
                        "score_mode": "avg",
                        "query": {
                            "query_string": {
                                "fields": ["attachments.attachment.content", "attachments.filename"],
                                "query": query,
                                "fuzziness": "AUTO"
                            }
                        }
                    }
                }
            )
        if len(query_fields) > 1:
            # With attachments
            return {
                "query": {
                    "bool": {
                        "should": query_fields
                    }
                }
            }
        else:
            # Without Attachments
            return {"query": query_fields[0]}

    def search_read(self, domain=None, fields=None, offset=0, limit=None, order=None):
        if self.env.context.get('elasticsearch', 0):
            if self._get_host():
                es = Elasticsearch(self._get_host())
                # wenn es keinen durchsuchbaren index gibt, führe normale suche durch
                if es.indices.exists(self._get_index_name()):
                    # Odoo Suchbegriffe und Elasticsearch Suchbegriffe seperieren
                    odoo_domain = list(domain)
                    es_domain = []
                    for i, arg in enumerate(odoo_domain):
                        if arg[0] == 'elastic_filter':
                            es_domain.append(arg[2])
                            odoo_domain[i][2] = False

                    # Elasticsearch Suche mit Begriffen aus elastic_domain
                    ids = []
                    scores = {}
                    for i, sub in enumerate(es_domain):
                        for char in escape_char:
                            # escape special characters
                            sub = sub.replace(char, '\\' + char)
                        es_domain[i] =  sub + "~"   # enable fuzzy search
                    query = " ".join(es_domain)

                    es_res = es.search(index=self._get_index_name(), doc_type='odoo_record',
                                       body=self.search_query(query), size=limit)

                    for hit in es_res['hits']['hits']:
                        ids.append(int(hit['_id']))
                        scores[int(hit['_id'])] = hit["_score"]
                        _logger.debug("\n\nScore: " + str(hit["_score"]))

                    # Suchbegriffe die tatsächlich in das Suchfeld eingegeben wurden
                    actual_query = [arg for arg in odoo_domain if not (type(arg) is str) and arg[0] not in fields]

                    if len(es_domain) == len(actual_query):
                        # Wenn eine reine Elastissearch Suche vorgenommen wurde, auch nur Odoo Records dieser Ergebnisse anzeigen
                        odoo_domain = [["id", "in", ids]] + odoo_domain

                    # Normale Odoo Suche
                    odoo_res = super(ElasticIndex, self).search(odoo_domain or [], offset=offset,
                                                                limit=limit, order=order)

                    # Record Id Felder zur Anzeige lesen
                    res = odoo_res.read(fields)

                    # Score zur Anzeige in der Oberfläche setzen
                    for result in res:
                        result['score'] = scores.get(result['id'], 0)

                    res = sorted(res, key=lambda k: k['score'], reverse=True)
                    return res
            else:
                raise UserError('Volltextsuche derzeit nicht verfügbar.')

        return super(ElasticIndex, self).search_read(domain=domain, fields=fields,
                                                     offset=offset, limit=limit, order=order)

    def cron_recompute_indices(self):
        # Delete all indices and index them again
        model_ids = self.env['ir.model'].search([('model', '!=', 'elastic.index')]).mapped('model')
        for model in model_ids:
            if hasattr(self.env[model], '_elastic_index_attachments'):
                timestamp = fields.datetime.now()
                self.env[model].remove_index()
                self.env[model].index()
                timestamp = fields.datetime.now() - timestamp
                count = len(self.env[model].search([]))
                _logger.info("\n %s: %d Records in %0.2fs" % (model, count, timestamp.total_seconds()))

    def _index(self):
        if self._get_host():  # wenn elasticsearch server läuft
            es = Elasticsearch(self._get_host())
            index_name = self._get_index_name()
            if not es.indices.exists(index_name):
                index_config = {}
                mapping = {}
                for field in self.elastic_fields():
                # Für html Felder muss ein analyzer im index mapping gesetzt werden, damit tags nicht gefunden werden
                    if self._fields[field].type == 'html':
                        mapping[field] = {
                            "type": "text",
                            "analyzer": "htmlStripAnalyzer"
                        }
                if mapping:
                    index_config.update(self._get_setting())

                # wenn Index nicht vorhanden, erstelle Index mit Mapping (falls Attachments indiziert werden
                if self._elastic_index_attachments:
                    mapping['attachments'] = {"type": "nested"}
                if self._elastic_index_message:
                    mapping['messages'] = {"type": "nested",
                                           "properties": {
                                               "subject": {"type": "text"},
                                               "body": {"type": "text",
                                                        "analyzer": "htmlStripAnalyzer"}
                                           }}

                index_config.update(self._get_mapping(mapping))
                es.indices.create(index=index_name, body=index_config)
                self = self.env[self._name].search([])

            if self._elastic_index_attachments:
                # Open Pipeline, to add attachment content in index document
                self._put_pipeline()

            # index updaten bzw befüllen
            fields = self.elastic_fields()
            for record in self:
                values = {}
                for field in fields:
                    # Add 'normal' fields to values to be indexed
                    if not record.__getattribute__(field):
                        continue
                    if record._fields[field].type in ['char', 'html', 'text']:
                        values[field] = record.__getattribute__(field)
                    elif record._fields[field].type == 'many2many':
                        values[field] = [x[1] for x in record.__getattribute__(field).name_get()]
                    else:
                        raise NotImplementedError('Field of type %s could not be indexed.' % record._fields[field].type)

                if self._elastic_index_message:
                    # Index Chatter Messages
                    message_ids = self.env['mail.message'].search([('model', '=', self._name),
                                                                   ('res_id', '=', record.id),
                                                                   ('message_type', 'in', ['comment', 'email'])])
                    if message_ids:
                        message_data = []
                        for message in message_ids:
                            message_data.append({
                                'subject': message.subject,
                                'body': message.body
                            })
                        values['messages'] = message_data


                if self._elastic_index_attachments:
                    # Index Attachments
                    attachment_ids = self.env['ir.attachment'].search([('res_model', '=', self._name),
                                                                       ('res_id', '=', record.id)])
                    if attachment_ids:
                        # Get binary data content of each attachment file
                        attachment_data = []
                        for file in attachment_ids:
                            if not file.datas:
                                continue
                            attachment_data.append({
                                'filename': file.datas_fname,
                                'id': file.id,
                                'data': bytes.decode(file.datas).replace("\n", "")
                            })
                        values['attachments'] = attachment_data

                        # Index record with attachment pipeline
                        es.index(index=index_name, doc_type='odoo_record', id=record.id, body=values,
                                 pipeline='attachment_pipeline')
                        continue
                # Index record without pipeline
                es.index(index=index_name, doc_type='odoo_record', id=record.id, body=values)

    def _get_host(self):
        host = str(config.get('elastic_host', ''))
        try:
            requests.get(host)
        except Exception:
            _logger.debug(u"Elasticsearch Server not running or config file not properly configured.")
            host = False
            pass
        return host

    def _get_index_name(self):
        # Index name : <prefix>.<db>.<model>
        return "%s.%s.%s" % (config.get('elastic_index_prefix', default='default'),
                             self._cr.dbname, self._name.replace('.', '_'))

    def _get_mapping(self, properties):
        #
        return {
            "mappings": {
                "odoo_record": {
                    "properties": properties
                }
            }
        }

    def _get_setting(self):
        return {
            "settings": {
                "analysis": {
                    "analyzer": {
                        "default": {
                            "type": "custom",
                            "tokenizer": "whitespace",
                            "filter": ["lowercase"]
                        },
                        "htmlStripAnalyzer": {
                            "type": "custom",
                            "tokenizer": "whitespace",
                            "filter": ["lowercase"],
                            "char_filter": [
                                "html_strip"
                            ]
                        }
                    }
                }
            }
        }


    def _put_pipeline(self):
        # Use  pipeline from ingest attachment plugin to extract
        # file attachments in common formats (PPT,XLS,PDF)

        es = Elasticsearch(self._get_host())
        p = IngestClient(es)
        p.put_pipeline(id='attachment_pipeline', body={
            "description": "Extract attachment information from arrays",
            "processors": [
                {
                    "foreach": {
                        "field": "attachments",
                        "processor": {
                            "attachment": {
                                "target_field": "_ingest._value.attachment",
                                "field": "_ingest._value.data",
                                "properties": ["content"]
                            }
                        }
                    }
                },
                {
                    "foreach": {
                        "field": "attachments",
                        "processor": {
                            "remove": {"field": "_ingest._value.data"}
                        }
                    }
                }
            ]
        })
