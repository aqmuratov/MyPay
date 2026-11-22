from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.db import transaction
from django.db.models import Q
from django.shortcuts import redirect, render

from .models import Transaction, Wallet
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
import csv
from datetime import timedelta
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.db import transaction
from django.db.models import Q, Sum
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone

from .models import Transaction, Wallet

def register(request):
    form = UserCreationForm(request.POST or None)
    if form.is_valid():
        user = form.save()
        Wallet.objects.create(user=user)
        login(request, user)
        return redirect('home')
    return render(request, 'registration/register.html', {'form': form})


@login_required
def home(request):
    wallet = request.user.wallet
    txs = Transaction.objects.filter(Q(sender=wallet) | Q(receiver=wallet))[:5]
    return render(request, 'home.html', {'wallet': wallet, 'txs': txs})


def fmt(n):
    return f'{int(n):,}'.replace(',', '\u00a0')


@login_required
def history(request):
    wallet = request.user.wallet
    now = timezone.localtime()
    base = Transaction.objects.filter(Q(sender=wallet) | Q(receiver=wallet))

    this_month = base.filter(created_at__year=now.year, created_at__month=now.month)
    month_in = this_month.filter(receiver=wallet).aggregate(s=Sum('amount'))['s'] or 0
    month_out = this_month.filter(sender=wallet).aggregate(s=Sum('amount'))['s'] or 0

    sel_type = request.GET.get('type', '')
    sel_period = request.GET.get('period', '')
    qs = base
    if sel_type == 'in':
        qs = qs.filter(receiver=wallet)
    elif sel_type == 'transfer':
        qs = qs.filter(sender=wallet, kind='transfer')
    elif sel_type == 'payment':
        qs = qs.filter(kind='payment')
    if sel_period == 'month':
        qs = qs.filter(created_at__year=now.year, created_at__month=now.month)
    elif sel_period == 'week':
        qs = qs.filter(created_at__gte=now - timedelta(days=7))

    icons = {s['name']: s['icon'] for s in SERVICES.values()}
    groups = []
    for t in qs.select_related('sender__user', 'receiver__user')[:200]:
        d = timezone.localtime(t.created_at)
        label = f'{d.day} {MONTHS[d.month - 1]}'
        out = t.sender_id == wallet.id

        if t.kind == 'payment':
            name, _, acct = t.title.partition(': ')
            title, sub, icon = name, acct or "To'lovlar", icons.get(name, 'i-wallet')
        elif out:
            title, sub, icon = t.title, "O'tkazmalar", 'i-transfer'
        else:
            who = t.sender.user.username if t.sender else "Noma'lum"
            title, sub, icon = f'{who} dan tushum', 'Tushumlar', 'i-transfer'

        if groups and groups[-1]['label'] == label:
            g = groups[-1]
        else:
            g = {'label': label, 'spent': 0, 'got': 0, 'items': []}
            groups.append(g)
        if out:
            g['spent'] += t.amount
        else:
            g['got'] += t.amount
        g['items'].append({
            'title': title, 'sub': sub, 'icon': icon, 'out': out,
            'amount': fmt(t.amount), 'time': d.strftime('%H:%M'),
        })

    for g in groups:
        g['spent_s'] = fmt(g['spent'])
        g['got_s'] = fmt(g['got'])

    return render(request, 'history.html', {
        'groups': groups,
        'month': MONTHS[now.month - 1].capitalize(),
        'month_in': fmt(month_in),
        'month_out': fmt(month_out),
        'sel_type': sel_type,
        'sel_period': sel_period,
    })


@login_required
def history_export(request):
    wallet = request.user.wallet
    resp = HttpResponse(content_type='text/csv; charset=utf-8')
    resp['Content-Disposition'] = 'attachment; filename="mypay_hisobot.csv"'
    resp.write('\ufeff')
    w = csv.writer(resp)
    w.writerow(['Sana', 'Turi', 'Izoh', 'Summa'])
    for t in Transaction.objects.filter(Q(sender=wallet) | Q(receiver=wallet)):
        sign = -1 if t.sender_id == wallet.id else 1
        w.writerow([
            timezone.localtime(t.created_at).strftime('%Y-%m-%d %H:%M'),
            t.kind, t.title, sign * t.amount,
        ])
    return resp


MONTHS = ['yanvar', 'fevral', 'mart', 'aprel', 'may', 'iyun',
          'iyul', 'avgust', 'sentabr', 'oktabr', 'noyabr', 'dekabr']


def _mask(u):
    if len(u) <= 3:
        return u[0] + '*' * (len(u) - 1)
    return u[:2] + '******' + u[-2:]


@login_required
def transfer(request):
    wallet = request.user.wallet
    qs = list(Transaction.objects
              .filter(sender=wallet, kind='transfer', receiver__isnull=False)
              .select_related('receiver__user')[:60])

    counts = {}
    for t in qs:
        u = t.receiver.user.username
        counts[u] = counts.get(u, 0) + 1

    since = timezone.now() - timedelta(hours=24)
    incoming = {}
    for t in (Transaction.objects
              .filter(receiver=wallet, kind='transfer', created_at__gte=since)
              .select_related('sender__user')):
        if t.sender:
            u = t.sender.user.username
            incoming[u] = incoming.get(u, 0) + 1

    seen, groups = set(), []
    for t in qs:
        u = t.receiver.user.username
        if u in seen:
            continue
        seen.add(u)
        d = timezone.localtime(t.created_at)
        label = f'{d.day} {MONTHS[d.month - 1]}'
        item = {
            'username': u, 'masked': _mask(u), 'initials': u[:2].upper(),
            'verified': counts[u] >= 2, 'new': incoming.get(u, 0),
        }
        if groups and groups[-1]['label'] == label:
            groups[-1]['items'].append(item)
        else:
            groups.append({'label': label, 'items': [item]})
    return render(request, 'transfer.html', {'groups': groups})


@login_required
def send(request):
    to = (request.POST.get('username') or request.GET.get('to') or '').strip()
    if request.method == 'POST':
        try:
            amount = Decimal(request.POST.get('amount', '0'))
        except InvalidOperation:
            amount = Decimal('0')

        if amount <= 0:
            messages.error(request, "Summa noto'g'ri")
        elif to == request.user.username:
            messages.error(request, "O'zingizga o'tkaza olmaysiz")
        else:
            try:
                with transaction.atomic():
                    sender = Wallet.objects.select_for_update().get(user=request.user)
                    receiver = Wallet.objects.select_for_update().get(user__username=to)
                    if sender.balance < amount:
                        raise ValueError("Mablag' yetarli emas")
                    sender.balance -= amount
                    receiver.balance += amount
                    sender.save()
                    receiver.save()
                    Transaction.objects.create(
                        sender=sender, receiver=receiver, amount=amount,
                        kind='transfer', title=f"{to} ga o'tkazma",
                    )
                messages.success(request, "O'tkazma bajarildi")
                return redirect('home')
            except Wallet.DoesNotExist:
                messages.error(request, 'Foydalanuvchi topilmadi')
            except ValueError as e:
                messages.error(request, str(e))
    return render(request, 'send.html', {'to': to})

SERVICES = {
    'mobile': {'name': 'Mobil aloqa', 'icon': 'i-phone', 'label': 'Telefon raqam'},
    'internet': {'name': 'Internet', 'icon': 's-globe', 'label': 'Shartnoma raqami'},
    'electric': {'name': 'Elektr energiya', 'icon': 's-bolt', 'label': 'Hisob raqami'},
    'gas': {'name': 'Tabiiy gaz', 'icon': 's-flame', 'label': 'Hisob raqami'},
    'water': {'name': 'Suv', 'icon': 's-drop', 'label': 'Hisob raqami'},
}


@login_required
def payments(request):
    wallet = request.user.wallet
    last = Transaction.objects.filter(sender=wallet, kind='payment').first()
    return render(request, 'payments.html', {'last': last})


@login_required
def pay(request, code):
    service = SERVICES.get(code)
    if not service:
        return redirect('payments')
    if request.method == 'POST':
        account = request.POST.get('account', '').strip()
        try:
            amount = Decimal(request.POST.get('amount', '0'))
        except InvalidOperation:
            amount = Decimal('0')
        if not account or amount <= 0:
            messages.error(request, "Ma'lumotlar noto'g'ri")
        else:
            try:
                with transaction.atomic():
                    sender = Wallet.objects.select_for_update().get(user=request.user)
                    if sender.balance < amount:
                        raise ValueError("Mablag' yetarli emas")
                    sender.balance -= amount
                    sender.save()
                    Transaction.objects.create(
                        sender=sender, amount=amount, kind='payment',
                        title=f"{service['name']}: {account}",
                    )
                messages.success(request, "To'lov bajarildi")
                return redirect('home')
            except ValueError as e:
                messages.error(request, str(e))
        return render(request, 'pay.html', {'service': service, 'prefill': request.GET.get('phone', '')})


def manifest(request):
    return JsonResponse({
        'name': 'MyPay',
        'short_name': 'MyPay',
        'start_url': '/',
        'display': 'standalone',
        'background_color': '#121214',
        'theme_color': '#121214',
        'icons': [
            {'src': '/static/icon-192.png', 'sizes': '192x192', 'type': 'image/png'},
            {'src': '/static/icon-512.png', 'sizes': '512x512', 'type': 'image/png'},
        ],
    })


def service_worker(request):
    js = """
self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', e => e.waitUntil(clients.claim()));
self.addEventListener('fetch', () => {});
"""
    return HttpResponse(js, content_type='application/javascript')