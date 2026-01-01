import json
import re
from dataclasses import dataclass
from flask import Blueprint, current_app, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
import requests

bp = Blueprint('integrations', __name__)


# AI Assistant
@bp.route('/ai_assistant', methods=['GET', 'POST'])
def ai_assistant():
    from flask import session
    from ..models import User
    
    # Get user from session or current_user
    user = None
    user_id = None
    
    if current_user.is_authenticated:
        user = current_user
        user_id = current_user.id
    else:
        user_id = session.get('student_user_id') or session.get('user_id')
        if user_id:
            user = User.query.get(user_id)
    
    if not user:
        flash('Please enter your Name and System ID to access AI Assistant.', 'info')
        return redirect(url_for('main.index'))
    if request.method == 'POST':
        question = (request.form.get('question') or '').strip()
        if not question:
            flash('Please enter a question.', 'warning')
            return redirect(url_for('integrations.ai_assistant'))
        api_key = current_app.config.get('DEEPINFRA_API_KEY')
        api_url = current_app.config.get('DEEPINFRA_API_URL', 'https://api.deepinfra.com/v1/openai/chat/completions')
        if not api_key:
            flash('AI API key not configured.', 'danger')
            return redirect(url_for('integrations.ai_assistant'))
        try:
            headers = {
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json',
            }
            data = {
                'model': 'meta-llama/Meta-Llama-3.1-8B-Instruct',
                'messages': [
                    {'role': 'system', 'content': 'You are a helpful assistant.'},
                    {'role': 'user', 'content': question},
                ],
                'temperature': 0.7,
            }
            resp = requests.post(api_url, headers=headers, data=json.dumps(data))
            resp.raise_for_status()
            answer = resp.json()['choices'][0]['message']['content']
            return render_template('ai_assistant.html', answer=answer, question=question)
        except Exception as e:
            flash(f'Error getting AI response: {str(e)}', 'danger')
            return redirect(url_for('integrations.ai_assistant'))
    return render_template('ai_assistant.html')


# WhatsApp Debug/Test
@dataclass
class WhatsAppDebugResult:
    ok: bool
    messages: list


@bp.route('/admin/debug-whatsapp', methods=['GET', 'POST'])
@login_required
def debug_whatsapp():
    if not getattr(current_user, 'is_admin', False):
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('main.health'))

    debug_results: list[str] = []

    if request.method == 'POST':
        test_phone = (request.form.get('test_phone') or '').strip()
        test_message = (request.form.get('test_message') or 'This is a test message.').strip()

        token = current_app.config.get('WHATSAPP_ACCESS_TOKEN')
        phone_id = current_app.config.get('WHATSAPP_PHONE_NUMBER_ID')
        debug_results.append('=== CONFIGURATION CHECK ===')
        debug_results.append(f"ACCESS_TOKEN: {'SET' if token else 'MISSING'}")
        debug_results.append(f"PHONE_NUMBER_ID: {phone_id or 'MISSING'}")

        if not token or not phone_id:
            return render_template('admin/debug_whatsapp.html', debug_results=debug_results)

        # Sanitize phone
        clean_phone = re.sub(r'[^0-9]', '', test_phone)
        debug_results.append('=== PHONE NUMBER VALIDATION ===')
        debug_results.append(f'Original: {test_phone}')
        debug_results.append(f'Cleaned: {clean_phone}')
        if not clean_phone or len(clean_phone) < 6 or len(clean_phone) > 15:
            debug_results.append(f'Invalid phone number length: {len(clean_phone) if clean_phone else 0}')
            return render_template('admin/debug_whatsapp.html', debug_results=debug_results)

        # Endpoint and payload
        url = f'https://graph.facebook.com/v22.0/{phone_id}/messages'
        headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
        payload = {
            'messaging_product': 'whatsapp',
            'to': clean_phone,
            'type': 'text',
            'text': {'body': test_message},
        }
        debug_results.append('=== API ENDPOINT TEST ===')
        debug_results.append(f'URL: {url}')

        try:
            r = requests.post(url, headers=headers, json=payload, timeout=20)
            debug_results.append(f'Status: {r.status_code}')
            try:
                debug_results.append(f'Response: {r.json()}')
            except Exception:
                debug_results.append(f'Response (text): {r.text[:500]}')
        except Exception as e:
            debug_results.append(f'EXCEPTION: {e}')

    return render_template('admin/debug_whatsapp.html', debug_results=debug_results)
