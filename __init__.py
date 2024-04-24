from app.utils.PluginClass import PluginClass
from flask_jwt_extended import jwt_required, get_jwt_identity
from flask import request
from app.utils import DatabaseHandler
from app.api.records.models import RecordUpdate
from celery import shared_task
import os
from bson.objectid import ObjectId
from dotenv import load_dotenv

load_dotenv()

mongodb = DatabaseHandler.DatabaseHandler()
WEB_FILES_PATH = os.environ.get('WEB_FILES_PATH', '')
ORIGINAL_FILES_PATH = os.environ.get('ORIGINAL_FILES_PATH', '')

class ExtendedPluginClass(PluginClass):
    def __init__(self, path, import_name, name, description, version, author, type, settings):
        super().__init__(path, __file__, import_name, name, description, version, author, type, settings)

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
        
    @shared_task(ignore_result=False, name='documentMakerMetadata.bulk')
    def bulk(body, user):
        pass        
    
plugin_info = {
    'name': 'Generar documentos a partir de metadatos',
    'description': 'Plugin para generar documentos a partir de metadatos usando plantillas predefinidas.',
    'version': '0.1',
    'author': 'Néstor Andrés Peña',
    'type': ['settings'],
    'settings': {
        'settings': [

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