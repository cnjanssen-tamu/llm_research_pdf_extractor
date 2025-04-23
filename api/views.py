from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.db.models import Q
from core.models import Document, ProcessingResult
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAuthenticated

class ResultDetail(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]
    
    def get(self, request, document_id):
        """
        Get processing results for a document.
        Returns both raw result and parsed JSON result.
        """
        try:
            # Ensure the document belongs to the requesting user
            document = Document.objects.get(
                Q(id=document_id) & 
                (Q(owner=request.user) | Q(shared_with=request.user))
            )
            
            # Get the latest processing result
            result = ProcessingResult.objects.filter(document=document).latest('created_at')
            
            # Prepare the response
            response_data = {
                'document_id': document_id,
                'created_at': result.created_at,
                'is_complete': result.is_complete,
                'raw_result': result.raw_result,
            }
            
            # Check if we have valid JSON
            if result.json_result:
                if isinstance(result.json_result, str):
                    # If stored as string, try to parse it
                    try:
                        from core.utils import extract_json_from_text
                        json_data = extract_json_from_text(result.json_result)
                        response_data['json_result'] = json_data
                    except Exception as e:
                        response_data['json_result'] = None
                        response_data['json_error'] = str(e)
                else:
                    # Already parsed JSON (dictionary)
                    response_data['json_result'] = result.json_result
            else:
                # No JSON stored, try to extract it from raw result
                try:
                    from core.utils import extract_json_from_text
                    response_data['json_result'] = extract_json_from_text(result.raw_result)
                except Exception as e:
                    response_data['json_error'] = str(e)
            
            return Response(response_data)
            
        except Document.DoesNotExist:
            return Response({"error": "Document not found"}, status=status.HTTP_404_NOT_FOUND)
        except ProcessingResult.DoesNotExist:
            return Response({"error": "No results found for this document"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR) 