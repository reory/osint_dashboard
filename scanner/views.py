"""Django webhook and UI views that receive scan results from FastAPI and
render OSINT search data to the dashboard."""

import os
import json
from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import requests
from .models import TargetSearch, DiscoveredProfile

@csrf_exempt
def webhook_update_status(request):
    """Receives status updates (running, completed, failed) from FastAPI."""

    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            search_id = data.get('search_id')
            status = data.get('status')
            
            # DEFENSIVE: Handle case where record was deleted mid-scan
            try:
                search_record = TargetSearch.objects.get(id=search_id)
                search_record.status = status
                search_record.save()
            except TargetSearch.DoesNotExist:
                return JsonResponse(
                    {'status': 'ignored', 'message': 'Record already cleared.'}
                )
                
            return JsonResponse({'status': 'success'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    return JsonResponse({'status': 'invalid method'}, status=405)

@csrf_exempt
def webhook_receive_result(request):
    """Receives individual discovered profiles from FastAPI and logs them to SQLite."""

    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            search_id = data.get('search_id')
            site_name = data.get('site_name')
            profile_url = data.get('profile_url')
            metadata = data.get('metadata', {})
            
            # DEFENSIVE: Handle case where record was deleted mid-scan
            try:
                search_record = TargetSearch.objects.get(id=search_id)
            except TargetSearch.DoesNotExist:
                return JsonResponse(
                    {'status': 'ignored', 'message': 'Record already cleared.'}
                )
            
            # Commit the match to the database rows cleanly
            DiscoveredProfile.objects.get_or_create(
                search=search_record,
                site_name=site_name,
                defaults={
                    'profile_url': profile_url,
                    'raw_json': metadata
                }
            )
            return JsonResponse({'status': 'success'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    return JsonResponse({'status': 'invalid method'}, status=405)

# --- USER INTERFACE UI VIEWS ---
def dashboard_home(request):
    """Renders the main dashboard page showing all search history."""

    searches = TargetSearch.objects.all().order_by('-created_at')
    return render(request, 'scanner/dashboard.html', {'searches': searches})


def trigger_scan(request):
    """Handles the form submission to initiate a new username search."""

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        
        if username:
            search_record, created = TargetSearch.objects.get_or_create(
                username=username,
                defaults={'status': 'pending'}
            )
            
            if not created:
                search_record.status = 'pending'
                search_record.profiles.all().delete()  # Clear old matches for a fresh scan
                search_record.save()
            
            # Trigger FastAPI background worker on port 8001
            fastapi_url = "http://127.0.0.1:8001/scan/"
            payload = {
                "username": username,
                "search_id": search_record.id
            }
            
            try:
                requests.post(fastapi_url, json=payload, timeout=3)
            except requests.exceptions.RequestException:
                search_record.status = 'failed'
                search_record.save()
                
    return redirect('dashboard_home')

def view_results(request, search_id):
    """
    Displays cleaned, human-readable OSINT profiles from the Maigret JSON report.
    """

    search = TargetSearch.objects.get(id=search_id)
    
    # Path configuration pointing directly inside your reports directory
    report_filename = f"report_{search.username.lower().strip()}_simple.json"
    report_path = os.path.join('reports', report_filename)
    
    cleaned_profiles = []
    
    if os.path.exists(report_path):
        try:
            with open(report_path, 'r', encoding='utf-8') as f:
                raw_data = json.load(f)
                
            # Loop through each site and pull out ONLY the human-friendly variables
            for site_name, data in raw_data.items():
                if not isinstance(data, dict):
                    continue
                
                # Check if Maigret confirmed a profile exists
                status_block = data.get('status', {})
                if not isinstance(status_block, dict):
                    status_block = {}
                    
                if status_block.get('status') == 'Claimed' or data.get('is_found'):
                    
                    # HARDENED CHECK: Ensure ids block is explicitly a dictionary
                    ids = status_block.get('ids', {})
                    if not isinstance(ids, dict):
                        ids = {}
                    
                    profile_info = {
                        'site': site_name,
                        'url': (
                            data.get('url_user') 
                            or status_block.get('url') 
                            or f"https://{site_name.lower()}.com/{search.username}",
                        ),
                        'fullname': (
                            ids.get('fullname')
                            or ids.get('nickname') 
                            or 'N/A',
                        ),
                        'bio': (
                            ids.get('bio') 
                            or ids.get('description') 
                            or 'No profile bio provided.',
                        ),
                        'location': (
                            ids.get('location') 
                            or 'Unknown Location',
                        ),
                        'image': ids.get('image') or None, # Captures profile pictures dynamically!
                        'tags': (
                            status_block.get('tags') 
                            if isinstance(status_block.get('tags'), list) 
                            else [],
                        ),
                        'followers': ids.get('follower_count') or None
                    }

                    cleaned_profiles.append(profile_info)
                    
        except Exception as e:
            print(f"Error compiling human-readable dictionary block: {e}")
            
    return render(request, 'scanner/results.html', {
        'search': search, 
        'cleaned_profiles': cleaned_profiles, 
    })

def clear_history(request):
    """Deletes all search history and discovered profiles from the database."""
    
    if request.method == 'POST':
        # Deleting the parent searches will automatically delete child profiles 
        # because of Django's on_delete=models.CASCADE setting!
        TargetSearch.objects.all().delete()
        
    return redirect('dashboard_home')