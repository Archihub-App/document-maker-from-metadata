from app.utils.PluginClass import PluginClass
from flask_jwt_extended import jwt_required, get_jwt_identity
from flask import request
from app.utils import DatabaseHandler
from app.utils import HookHandler
from app.api.records.models import RecordUpdate
from celery import shared_task
from app.api.users.services import has_role
import os
from bson.objectid import ObjectId
from dotenv import load_dotenv
import json

from app.api.types.services import get_all as get_all_types

load_dotenv()

mongodb = DatabaseHandler.DatabaseHandler()
hookHandler = HookHandler.HookHandler()
WEB_FILES_PATH = os.environ.get('WEB_FILES_PATH', '')
ORIGINAL_FILES_PATH = os.environ.get('ORIGINAL_FILES_PATH', '')
plugin_path = os.path.dirname(os.path.abspath(__file__))
template_path = os.path.join(plugin_path, 'templates')

class ExtendedPluginClass(PluginClass):
    def __init__(self, path, import_name, name, description, version, author, type, settings):
        super().__init__(path, __file__, import_name, name, description, version, author, type, settings)
        self.activate_settings()

    def test(self, body):
        print(body)
        print("HOLA")

    def activate_settings(self):
        current = self.get_plugin_settings()
        if current is None:
            return
        
        types = current['types_activation']
        for t in types:
            hookHandler.register('resource_create', self.test, int(t['order']))
            print(t)

    def add_routes(self):
        @self.route('/bulk', methods=['POST'])
        @jwt_required()
        def processing():
            current_user = get_jwt_identity()
            body = request.get_json()

            if 'post_type' not in body:
                return {'msg': 'No se especificó el tipo de contenido'}, 400
            
            if not self.has_role('admin', current_user) and not self.has_role('processing', current_user):
                return {'msg': 'No tiene permisos suficientes'}, 401

            task = self.bulk.delay(body, current_user)
            self.add_task_to_user(task.id, 'documentMakerMetadata.bulk', current_user, 'msg')
            
            return {'msg': 'Se agregó la tarea a la fila de procesamientos'}, 201
        
    def get_settings(self):
        @self.route('/settings/<type>', methods=['GET'])
        @jwt_required()
        def get_settings(type):
            try:
                current_user = get_jwt_identity()

                if not has_role(current_user, 'admin') and not has_role(current_user, 'processing'):
                    return {'msg': 'No tiene permisos suficientes'}, 401
                
                types = get_all_types()
                if isinstance(types, list):
                    types = tuple(types)[0]

                current = self.get_plugin_settings()

                resp = {**self.settings}

                template_folders = os.listdir(template_path)

                resp['settings'][1]['fields'] = [
                    {
                        'type': 'select',
                        'id': 'type',
                        'default': '',
                        'options': [{'value': t['slug'], 'label': t['name']} for t in types],
                        'required': True
                    },
                    {
                        'type': 'select',
                        'id': 'template',
                        'default': '',
                        'options': [{'value': t, 'label': t} for t in template_folders],
                        'required': True
                    },
                    {
                        'type': 'number',
                        'id': 'order',
                        'default': 0,
                        'required': True
                    }
                ]
                
                if current is None:
                    resp['settings'][1]['default'] = []
                    
                else:
                    resp['settings'][1]['default'] = current['types_activation']

                
                if type == 'all':
                    return resp
                elif type == 'settings':
                    return resp['settings']
                else:
                    return resp['settings_' + type]
            except Exception as e:
                return {'msg': str(e)}, 500
            
        @self.route('/settings', methods=['POST'])
        @jwt_required()
        def set_settings_update():
            try:
                current_user = get_jwt_identity()

                if not has_role(current_user, 'admin') and not has_role(current_user, 'processing'):
                    return {'msg': 'No tiene permisos suficientes'}, 401
                
                body = request.form.to_dict()
                data = body['data']
                data = json.loads(data)

                types = data['types_activation']
                for t in types:
                    if t['type'] == '' or t['template'] == '':
                        return {'msg': 'Debe seleccionar un tipo de contenido y una plantilla'}, 400
                    if 'order' not in t:
                        t['order'] = '0'

                self.set_plugin_settings(data)
                self.activate_settings()

                return {'msg': 'Configuración guardada'}, 200
            
            except Exception as e:
                return {'msg': str(e)}, 500
        
    @shared_task(ignore_result=False, name='documentMakerMetadata.bulk')
    def bulk(body, user):
        pass        
    
plugin_info = {
    'name': 'Generar documentos a partir de metadatos',
    'description': 'Plugin para generar documentos a partir de metadatos usando plantillas predefinidas.',
    'version': '0.1',
    'author': 'Néstor Andrés Peña',
    'type': ['settings', 'bulk'],
    'settings': {
        'settings': [
            {
                'type': 'instructions',
                'title': 'Instrucciones',
                'text': 'Este plugin permite generar documentos a partir de metadatos usando plantillas predefinidas. Para configurar el plugin, seleccione el tipo de contenido y la plantilla a usar. Estos documentos se generarán al crear o actualizar un registro con el tipo de contenido seleccionado en el gestor documental.',
            },
            {
                'type': 'multiple',
                'title': 'Tipos de contenido a generar',
                'id': 'types_activation',
                'fields': []
            }
        ],
        'settings_bulk': [
            {
                'type':  'instructions',
                'title': 'Instrucciones',
                'text': '',
            }
        ]
    }
}