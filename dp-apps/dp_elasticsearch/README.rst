=======================
Elastic Search for Odoo
=======================



Add Model to Elasticsearch
==========================

| in dp_custom:
| **__manifest__.py**
| add dp_elasticsearch and model which needs to be searchable to dependencies

::

    'depends': [
        '< model >',
        'dp_elasticsearch'
    ]



| **models/<model_file_name>.py**
| inherit model and elastic.index

::

    class < ModelName >(models.Model):
        _name = "< model.name >"
        _inherit = ["< model.name >", "elastic.index"]

        def elastic_fields(self):
        # Add fields from model you want to be searchable by elasticsearch
            res = super(< ModelName >, self).elastic_fields()
            return res + ["categ_ids", "name"]


| **models/__init__.py:**

::

    from . import < model_file_name >



| **views/< model_view >.xml:**
| add elasticsearch filter to models search view
| add score to models tree view

::

    <odoo>
        <record id="elastic_< model_name >_search_view" model="ir.ui.view">
            <field name="name">elastic.< model_name >.search.view</field>
            <field name="model">< model.name ></field>
            <field name="inherit_id" ref="< model >.< model_search_view >"/>
            <field name="arch" type="xml">
                <field name="< field in view >" position="before">
                    <field name="elastic_filter" string="Volltextsuche"
                        context="{'elasticsearch': 1}"/>
                </field>
            </field>
        </record>

        <record id="elastic_< model_name >_tree_inherit" model="ir.ui.view">
            <field name="name">elastic_< model_name >_tree_inherit</field>
            <field name="model">< model.name ></field>
            <field name="inherit_id" ref=" < model >.< model_tree_view > "/>
            <field name="arch" type="xml">
                <xpath expr="//tree" position="inside">
                    <field name="score"
                        attrs="{'invisible': [('score', '=', 0)]}"/>
                </xpath>
            </field>
        </record>

    </odoo>


Config File
===========

::

    elastic_host = <elasticsearch server host> # z.b. http://172.19.0.1:9200
    elastic_index_prefix = dev # dev or prod


Setup
=====

Docker:
-------

- to run Elasticsearch Server
- https://docs.docker.com/install/linux/docker-ce/ubuntu/#install-docker-ce-1

Docker-Compose:
----------------

- (sudo) pip install docker-compose

Elastic-Stack:
--------------

- Clone Docker Compose File https://github.com/elastic/stack-docker
- Set max_map_count to at least 262144 as root: sudo sysctl -w vm.max_map_count=262144
- set working directories and pwd in stack-docker/setup.yml
- in /stack-docker/config/kibana/kibana.yml set https://elastic... to http
- in stack-docker/config/elasticsearch/elasticsearch.yml set xpath.security to false
- Start docker containers with: sudo docker-compose -f setup.yml up
- copy password
- check if containers are running: docker-compose ps
- install python package: pip install elasticsearch
- install attachment plugin:
  - go into elasticsearch bash: docker-compose exec elasticsearch bash
  - install ingest-attachment: bin/elasticsearch-plugin install ingest-attachment
- container restarten: docker-compose restart elasticsearch


Setup Elastic Server:
----------------------

| add host to config file
| find host : docker inspect elasticsearch

- z.B. "Gateway": "172.19.0.1",
