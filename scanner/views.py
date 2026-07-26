"""Django webhook and UI views that receive scan results from FastAPI and
render OSINT search data to the dashboard."""

import json
import logging
import os

import requests
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.csrf import csrf_exempt

from .models import DiscoveredProfile, TargetSearch

logger = logging.getLogger(__name__)


@csrf_exempt
def webhook_update_status(request):
    """Receives status updates (running, completed, failed) from FastAPI."""

    if request.method != 'POST':
        return JsonResponse({'status': 'invalid method'}, status=405)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError as e:
        logger.warning("webhook_update_status: malformed JSON body: %s", e)
        return JsonResponse({'status': 'error', 'message': 'Invalid JSON payload'}, status=400)

    search_id = data.get('search_id')
    status = data.get('status')

    if not search_id or not status:
        logger.warning("webhook_update_status: missing search_id/status in payload: %r", data)
        return JsonResponse({'status': 'error', 'message': 'search_id and status are required'}, status=400)

    try:
        search_record = TargetSearch.objects.get(id=search_id)
    except TargetSearch.DoesNotExist:
        logger.info("webhook_update_status: search_id=%s no longer exists (cleared mid-scan)", search_id)
        return JsonResponse({'status': 'ignored', 'message': 'Record already cleared.'})
    except TargetSearch.MultipleObjectsReturned as e:
        logger.error("webhook_update_status: duplicate records for search_id=%s: %s", search_id, e)
        return JsonResponse({'status': 'error', 'message': 'Duplicate search records'}, status=500)

    search_record.status = status
    try:
        search_record.save()
    except Exception:
        # Catch-all only at the DB-write boundary, and logged with full context
        logger.exception("webhook_update_status: failed saving search_id=%s status=%s", search_id, status)
        return JsonResponse({'status': 'error', 'message': 'Failed to persist status update'}, status=500)

    return JsonResponse({'status': 'success'})


@csrf_exempt
def webhook_receive_result(request):
    """Receives individual discovered profiles from FastAPI and logs them to SQLite."""

    if request.method != 'POST':
        return JsonResponse({'status': 'invalid method'}, status=405)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError as e:
        logger.warning("webhook_receive_result: malformed JSON body: %s", e)
        return JsonResponse({'status': 'error', 'message': 'Invalid JSON payload'}, status=400)

    search_id = data.get('search_id')
    site_name = data.get('site_name')
    profile_url = data.get('profile_url')
    metadata = data.get('metadata', {})

    if not search_id or not site_name:
        logger.warning("webhook_receive_result: missing search_id/site_name in payload: %r", data)
        return JsonResponse({'status': 'error', 'message': 'search_id and site_name are required'}, status=400)

    try:
        search_record = TargetSearch.objects.get(id=search_id)
    except TargetSearch.DoesNotExist:
        logger.info("webhook_receive_result: search_id=%s no longer exists (cleared mid-scan)", search_id)
        return JsonResponse({'status': 'ignored', 'message': 'Record already cleared.'})
    except TargetSearch.MultipleObjectsReturned as e:
        logger.error("webhook_receive_result: duplicate records for search_id=%s: %s", search_id, e)
        return JsonResponse({'status': 'error', 'message': 'Duplicate search records'}, status=500)

    try:
        DiscoveredProfile.objects.get_or_create(
            search=search_record,
            site_name=site_name,
            defaults={
                'profile_url': profile_url,
                'raw_json': metadata
            }
        )
    except Exception:
        # Catch-all only at the DB-write boundary, and logged with full context
        logger.exception(
            "webhook_receive_result: failed writing profile search_id=%s site=%s", search_id, site_name
        )
        return JsonResponse({'status': 'error', 'message': 'Failed to persist discovered profile'}, status=500)

    return JsonResponse({'status': 'success'})


# --- USER INTERFACE UI VIEWS ---
def dashboard_home(request):
    """Renders the main dashboard page showing all search history."""

    searches = TargetSearch.objects.all().order_by('-created_at')
    return render(request, 'scanner/dashboard.html', {'searches': searches})


def trigger_scan(request):
    """Handles the form submission to initiate a new username search."""

    if request.method != 'POST':
        return redirect('dashboard_home')

    username = request.POST.get('username', '').strip()
    if not username:
        return redirect('dashboard_home')

    search_record, created = TargetSearch.objects.get_or_create(
        username=username,
        defaults={'status': 'pending'}
    )

    if not created:
        search_record.status = 'pending'
        search_record.profiles.all().delete()  # Clear old matches for a fresh scan
        search_record.save()

    fastapi_url = "http://127.0.0.1:8001/scan/"
    payload = {
        "username": username,
        "search_id": search_record.id
    }

    try:
        requests.post(fastapi_url, json=payload, timeout=3)
    except requests.exceptions.Timeout:
        logger.warning("trigger_scan: FastAPI worker timed out for username=%s", username)
        search_record.status = 'failed'
        search_record.save()
    except requests.exceptions.ConnectionError as e:
        logger.error("trigger_scan: could not reach FastAPI worker for username=%s: %s", username, e)
        search_record.status = 'failed'
        search_record.save()
    except requests.exceptions.RequestException:
        logger.exception("trigger_scan: unexpected request error for username=%s", username)
        search_record.status = 'failed'
        search_record.save()

    return redirect('dashboard_home')


def view_results(request, search_id):
    """
    Displays cleaned, human-readable OSINT profiles from the Maigret JSON report.
    """

    search = TargetSearch.objects.get(id=search_id)

    report_filename = f"report_{search.username.lower().strip()}_simple.json"
    report_path = os.path.join('reports', report_filename)

    cleaned_profiles = []

    if os.path.exists(report_path):
        try:
            with open(report_path, 'r', encoding='utf-8') as f:
                raw_data = json.load(f)
        except json.JSONDecodeError as e:
            logger.error("view_results: corrupt JSON report at %s: %s", report_path, e)
            raw_data = {}
        except OSError as e:
            logger.error("view_results: could not read report file %s: %s", report_path, e)
            raw_data = {}
        else:
            for site_name, data in raw_data.items():
                if not isinstance(data, dict):
                    continue

                status_block = data.get('status', {})
                if not isinstance(status_block, dict):
                    status_block = {}

                if status_block.get('status') == 'Claimed' or data.get('is_found'):
                    ids = status_block.get('ids', {})
                    if not isinstance(ids, dict):
                        ids = {}

                    try:
                        profile_info = {
                            'site': site_name,
                            'url': (
                                data.get('url_user')
                                or status_block.get('url')
                                or f"https://{site_name.lower()}.com/{search.username}"
                            ),
                            'fullname': (
                                ids.get('fullname')
                                or ids.get('nickname')
                                or 'N/A'
                            ),
                            'bio': (
                                ids.get('bio')
                                or ids.get('description')
                                or 'No profile bio provided.'
                            ),
                            'location': (
                                ids.get('location')
                                or 'Unknown Location'
                            ),
                            'image': ids.get('image') or None,
                            'tags': (
                                status_block.get('tags')
                                if isinstance(status_block.get('tags'), list)
                                else []
                            ),
                            'followers': ids.get('follower_count') or None
                        }
                    except (TypeError, AttributeError) as e:
                        # e.g. site_name.lower() failing because site_name wasn't a string
                        logger.warning(
                            "view_results: malformed entry for site=%r in %s: %s",
                            site_name, report_path, e
                        )
                        continue

                    cleaned_profiles.append(profile_info)

    return render(request, 'scanner/results.html', {
        'search': search,
        'cleaned_profiles': cleaned_profiles,
    })


def clear_history(request):
    """Deletes all search history and discovered profiles from the database."""

    if request.method == 'POST':
        TargetSearch.objects.all().delete()

    return redirect('dashboard_home')