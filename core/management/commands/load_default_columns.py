from django.core.management.base import BaseCommand
from core.models import ColumnDefinition
import json
import os

class Command(BaseCommand):
    help = 'Load default column definitions based on the human_vs_llm extraction schema'

    def add_arguments(self, parser):
        parser.add_argument(
            '--file',
            default='/Users/chrisjanssen/Insync/cnjanssen@tamu.edu/Google Drive/COM/Research/human_vs_llm/human_reviewer_django/extraction_schema_dump.json',
            help='Path to the JSON file containing the extraction schema'
        )
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear existing columns before loading new ones'
        )

    def handle(self, *args, **options):
        file_path = options['file']
        clear = options['clear']

        if not os.path.exists(file_path):
            self.stdout.write(self.style.ERROR(f'File not found: {file_path}'))
            return

        # Clear existing columns if requested
        if clear:
            self.stdout.write(self.style.WARNING('Clearing existing column definitions...'))
            ColumnDefinition.objects.all().delete()

        # Load the JSON file
        with open(file_path, 'r') as f:
            # The file might be a list of objects or just a JSON object
            try:
                # First try to read as JSON array with objects
                data = json.load(f)
                if isinstance(data, dict):
                    data = [data]
            except json.JSONDecodeError:
                # If that fails, try to read line by line
                f.seek(0)
                data = []
                for line in f:
                    try:
                        obj = json.loads(line.strip())
                        data.append(obj)
                    except json.JSONDecodeError:
                        continue

        # Category mappings based on field descriptions and contexts
        category_mappings = {
            # Presenting Symptoms
            'loss_of_bladder_control': 'presentation',
            'parasthesia': 'presentation',
            'neruopathyradiculopathy': 'presentation',
            'mass': 'presentation',
            'headache': 'presentation',
            'ue_pain': 'presentation',
            'ue_weakness': 'presentation',
            'le_weakness': 'presentation',
            'tetraparesis': 'presentation',
            'neck_pain': 'presentation',
            'facial_pain': 'presentation',
            'gait_disturbance': 'presentation',
            'nausea': 'presentation',
            'duration_of_symptoms_in_months': 'clinical',
            
            # Co-morbidities
            'co_morbidities': 'symptoms',
            'spastiicty': 'symptoms',
            'muscle_atrophy': 'symptoms',
            'proptosis_1': 'symptoms',
            'visual_deficits': 'symptoms',
            'abnormal_reflexes': 'symptoms',
            'sensory_deficits': 'symptoms',
            'ue_weakness_1': 'symptoms',
            'le_weakness_1': 'symptoms',
            'hemiparesis': 'symptoms',
            'hyperreflexia': 'symptoms',
            'hoffman': 'symptoms',
            'babinski': 'symptoms',
            
            # Imaging
            'imaging_modalities_for_workup': 'imaging',
            'cranial_vs_spinal': 'imaging',
            'location': 'imaging',
            'level': 'imaging',
            'single_vs_multi': 'imaging',
            'contrast_enhancment_pattern': 'imaging',
            'adjacent_bone': 'imaging',
            'bone_yesno': 'imaging',
            'invasion_of': 'imaging',
            'invasion_yn': 'imaging',
            'location_of_invasion': 'imaging',
            'intradural_extension': 'imaging',
            'intradural_compnent': 'imaging',
            'post_op_imaging': 'imaging',
            
            # Workup
            'preoperation_biopsy': 'workup',
            
            # Treatment
            'neoadjuvant_therapy_yn': 'treatment',
            'if_yes_what_kind_chemo_radiation_both': 'treatment',
            'surgery_type': 'treatment',
            'surgical_approach': 'treatment',
            'resection_amount': 'treatment',
            'adjuvant_therapy_yn': 'treatment',
            'what_therapy_chemo_radiation_both_srs_etc': 'treatment',
            
            # Post-op
            'surgical_complications': 'postop',
            'postop_complications': 'postop',
            'residual': 'postop',
            
            # Pathology/IHC staining
            'ema': 'pathology',
            'vimentin': 'pathology',
            'ck': 'pathology',
            'progesterone': 'pathology',
            'sstr2': 'pathology',
            'cd99': 'pathology',
            'cd34': 'pathology',
            'ck_1': 'pathology',
            'sox10': 'pathology',
            's100': 'pathology',
            'gfap': 'pathology',
            'vimentin_1': 'pathology',
            'ki67': 'pathology',
            'who_grade': 'pathology',
            'subtype': 'pathology',
            
            # Follow-up
            'follow_up_intervention_repeat_surgery_etc': 'followup',
            'if_yes_what_procedure': 'followup',
            
            # Last follow-up
            'last_follow_up_months': 'lastfollowup',
            'symptom_assessment': 'lastfollowup',
            'recurrence': 'lastfollowup',
            'recurrance': 'outcome',
            'progression': 'outcome',
            'progression_free_survival': 'outcome',
            'disease_free_survival_months': 'outcome',
            'status_ad': 'outcome'
        }

        # Data type mappings
        data_type_mappings = {
            'BOOLEAN': 'boolean',
            'TEXT': 'string',
            'TEXTAREA': 'string',
            'NUMBER': 'float',
            'SELECT': 'enum'
        }

        # Process each schema item
        created_count = 0
        for item in data:
            # Extract fields from the extraction schema
            if "fields" not in item:
                continue
                
            fields = item['fields']
            field_name = fields.get('field_name', '')
            field_label = fields.get('field_label', '')
            field_type = fields.get('field_type', '')
            description = fields.get('description', '')
            choices = fields.get('choices', '')
            is_required = not fields.get('is_required', True)  # Invert for 'optional'
            order = fields.get('order', 0)
            
            # Skip if field_name is empty
            if not field_name:
                continue
                
            # Map to appropriate category and data type
            category = category_mappings.get(field_name, 'clinical')  # Default to clinical
            data_type = data_type_mappings.get(field_type, 'string')  # Default to string
            
            # Prepare enum_values if applicable
            enum_values = None
            if choices and data_type == 'enum':
                enum_values = choices.split(',')
            
            # Create or update the column definition
            column, created = ColumnDefinition.objects.update_or_create(
                name=field_name,
                defaults={
                    'description': f"{field_label}: {description}" if description else field_label,
                    'include_confidence': True,
                    'optional': is_required,
                    'category': category,
                    'data_type': data_type,
                    'enum_values': enum_values,
                    'order': order
                }
            )
            
            if created:
                created_count += 1
                self.stdout.write(self.style.SUCCESS(f'Created column: {field_name}'))
            else:
                self.stdout.write(self.style.WARNING(f'Updated column: {field_name}'))
        
        self.stdout.write(self.style.SUCCESS(f'Successfully created {created_count} column definitions')) 