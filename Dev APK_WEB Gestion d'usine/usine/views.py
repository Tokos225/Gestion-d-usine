from django.shortcuts import render
from django.contrib.auth.models import User, Group
from django.db import connection
import uuid
from django.db.models import Sum
from django.db.models.functions import Coalesce
from django.db.models import F, Sum
from django.db.models.functions import Coalesce

# Create your views here.


from datetime import datetime, timedelta
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from .models import (
    Piece, Fournisseur, AchatPiece,
    TypeIncident, Incident,
    Maintenance, ConsommerPiece
)


def _groupe_principal(user):
    if user.is_superuser:
        return 'Responsable'
    noms = set(user.groups.values_list('name', flat=True))
    if 'Maintenance' in noms:
        return 'Maintenance'
    if 'Stocks' in noms:
        return 'Stocks'
    if 'Responsable' in noms:
        return 'Responsable'
    return 'Standard'


def _minutes_depuis_duree(duree):
    if not duree:
        return 0
    return int(duree.total_seconds() // 60)


def connexion(request):
    if request.user.is_authenticated:
        return redirect('accueil')

    erreur = None
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect('accueil')
        erreur = "Identifiant ou mot de passe incorrect."

    return render(request, 'usine/connexion.html', {'erreur': erreur})

def inscription(request):
    if request.user.is_authenticated:
        return redirect('accueil')

    erreur = None
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        password2 = request.POST.get('password2', '')
        role = request.POST.get('role', 'Maintenance')

        if not username or not password:
            erreur = "Veuillez remplir tous les champs obligatoires."
        elif password != password2:
            erreur = "Les deux mots de passe ne correspondent pas."
        elif User.objects.filter(username=username).exists():
            erreur = "Cet identifiant est déjà utilisé."
        else:
            user = User.objects.create_user(username=username, password=password)
            groupe, _ = Group.objects.get_or_create(name=role)
            user.groups.add(groupe)
            login(request, user)
            return redirect('accueil')

    return render(request, 'usine/inscription.html', {'erreur': erreur})

def deconnexion(request):
    logout(request)
    return redirect('connexion')


@login_required
def accueil(request):
    role = _groupe_principal(request.user)
    if role == 'Maintenance':
        return redirect('espace_maintenance')
    if role == 'Stocks':
        return redirect('espace_stocks')
    return redirect('espace_responsable')
# ==========================================
# 1. APPROVISIONNEMENT DES PIECES (STOCKS)
# ==========================================
@login_required
def espace_stocks(request):
    erreur = None
    succes = request.session.pop('succes_stocks', None)
    erreur_session = request.session.pop('erreur_stocks', None)
    if erreur_session:
        erreur = erreur_session

    if request.method == 'POST':
        action = request.POST.get('action')
        try:
            if action == 'fournisseur':
                code_fourn = request.POST['code_fournisseur'].strip().upper()
                raison_soc = request.POST['raison_sociale'].strip()
                adresse_fourn = request.POST.get('adresse', '').strip()
                tel_fourn = request.POST.get('telephone', '').strip()

                _, cree = Fournisseur.objects.update_or_create(
                    code_fournisseur=code_fourn,
                    defaults={
                        'raison_sociale': raison_soc,
                        'adresse': adresse_fourn,
                        'telephone': tel_fourn,
                    },
                )
                if cree:
                    request.session['succes_stocks'] = f"Fournisseur {code_fourn} ajouté avec succès."
                else:
                    request.session['succes_stocks'] = f"Fournisseur {code_fourn} mis à jour."

            elif action == 'modifier_fournisseur':
                fourn = get_object_or_404(
                    Fournisseur, code_fournisseur=request.POST['code_fournisseur']
                )
                fourn.raison_sociale = request.POST['raison_sociale'].strip()
                fourn.adresse = request.POST.get('adresse', '').strip()
                fourn.telephone = request.POST.get('telephone', '').strip()
                fourn.save()
                request.session['succes_stocks'] = (
                    f"Fournisseur {fourn.code_fournisseur} modifié."
                )

            elif action == 'supprimer_fournisseur':
                fourn = get_object_or_404(
                    Fournisseur, code_fournisseur=request.POST['code_fournisseur']
                )
                code = fourn.code_fournisseur
                with connection.cursor() as cursor:
                    cursor.execute(
                        "DELETE FROM achat_piece WHERE code_fournisseur = %s",
                        [code],
                    )
                fourn.delete()
                request.session['succes_stocks'] = f"Fournisseur {code} supprimé."

            elif action == 'piece':
                ref = request.POST['ref_piece'].strip().upper()
                qte_initiale = int(request.POST.get('qte_stock') or 0)
                Piece.objects.create(
                    ref_piece=ref,
                    libelle=request.POST['libelle'].strip(),
                    prix_unitaire_ht=request.POST['prix_unitaire_ht'],
                    qte_stock=max(0, qte_initiale),
                )
                request.session['succes_stocks'] = f"Pièce {ref} ajoutée au stock."

            elif action == 'modifier_piece':
                piece = get_object_or_404(Piece, ref_piece=request.POST['ref_piece'])
                piece.libelle = request.POST['libelle'].strip()
                piece.prix_unitaire_ht = request.POST['prix_unitaire_ht']
                piece.qte_stock = max(0, int(request.POST['qte_stock']))
                piece.save()
                request.session['succes_stocks'] = f"Pièce {piece.ref_piece} mise à jour."

            elif action == 'supprimer_piece':
                piece = get_object_or_404(Piece, ref_piece=request.POST['ref_piece'])
                ref = piece.ref_piece
                with connection.cursor() as cursor:
                    cursor.execute(
                        "DELETE FROM consommer_piece WHERE ref_piece = %s",
                        [ref],
                    )
                    cursor.execute(
                        "DELETE FROM achat_piece WHERE ref_piece = %s",
                        [ref],
                    )
                piece.delete()
                request.session['succes_stocks'] = f"Pièce {ref} supprimée."

            elif action == 'achat':
                ref_piece = request.POST['ref_piece'].strip().upper()
                libelle_saisi = request.POST.get('libelle_piece', '').strip() or f"Pièce {ref_piece}"
                prix_achat = request.POST['prix_achat']
                qte_achetee = int(request.POST['quantite_achetee'])
                if qte_achetee <= 0:
                    raise ValueError("La quantité achetée doit être supérieure à 0.")

                piece, _ = Piece.objects.get_or_create(
                    ref_piece=ref_piece,
                    defaults={
                        'libelle': libelle_saisi,
                        'prix_unitaire_ht': prix_achat,
                        'qte_stock': 0,
                    },
                )

                code_fourn = request.POST['code_fournisseur'].strip().upper()
                raison_saisie = request.POST.get('raison_sociale', '').strip() or f"Fournisseur {code_fourn}"
                fournisseur, _ = Fournisseur.objects.get_or_create(
                    code_fournisseur=code_fourn,
                    defaults={
                        'raison_sociale': raison_saisie,
                        'adresse': '',
                        'telephone': '',
                    },
                )

                AchatPiece.objects.create(
                    ref_piece=piece,
                    code_fournisseur=fournisseur,
                    prix_achat=prix_achat,
                    date_achat=request.POST.get('date_achat') or timezone.now().date(),
                    quantite_achetee=qte_achetee,
                )
                # Décommente la ligne suivante uniquement si tu n'as PAS de trigger SQL qui incrémente déjà qte_stock à l'INSERT :
                # Piece.objects.filter(pk=piece.pk).update(qte_stock=F('qte_stock') + qte_achetee)
                request.session['succes_stocks'] = (
                    f"Arrivage enregistré (+{qte_achetee} pour {piece.ref_piece} chez {fournisseur.code_fournisseur})."
                )

            elif action == 'modifier_achat':
                achat = get_object_or_404(AchatPiece, id_achat=request.POST['id_achat'])
                ancienne_piece = achat.ref_piece
                ancienne_qte = achat.quantite_achetee

                ref_piece = request.POST['ref_piece'].strip().upper()
                nouvelle_piece, _ = Piece.objects.get_or_create(
                    ref_piece=ref_piece,
                    defaults={
                        'libelle': f"Pièce {ref_piece}",
                        'prix_unitaire_ht': request.POST['prix_achat'],
                        'qte_stock': 0,
                    },
                )

                code_fourn = request.POST['code_fournisseur'].strip().upper()
                fournisseur, _ = Fournisseur.objects.get_or_create(
                    code_fournisseur=code_fourn,
                    defaults={
                        'raison_sociale': f"Fournisseur {code_fourn}",
                        'adresse': '',
                        'telephone': '',
                    },
                )

                nouvelle_qte = int(request.POST['quantite_achetee'])
                if nouvelle_qte <= 0:
                    raise ValueError("La quantité achetée doit être supérieure à 0.")

                achat.ref_piece = nouvelle_piece
                achat.code_fournisseur = fournisseur
                achat.prix_achat = request.POST['prix_achat']
                achat.quantite_achetee = nouvelle_qte
                if request.POST.get('date_achat'):
                    achat.date_achat = request.POST['date_achat']
                achat.save()

                Piece.objects.filter(pk=ancienne_piece.pk).update(
                    qte_stock=F('qte_stock') - ancienne_qte
                )
                Piece.objects.filter(pk=nouvelle_piece.pk).update(
                    qte_stock=F('qte_stock') + nouvelle_qte
                )
                request.session['succes_stocks'] = f"Achat #{achat.id_achat} modifié."

            elif action == 'supprimer_achat':
                achat = get_object_or_404(AchatPiece, id_achat=request.POST['id_achat'])
                ref_p = achat.ref_piece_id
                qte_a = achat.quantite_achetee
                achat.delete()
                Piece.objects.filter(pk=ref_p).update(
                    qte_stock=F('qte_stock') - qte_a
                )
                request.session['succes_stocks'] = f"Achat #{achat.id_achat} supprimé."

            return redirect('espace_stocks')
        except Exception as e:
            request.session['erreur_stocks'] = str(e)
            return redirect('espace_stocks')

    piece_a_modifier = None
    if request.GET.get('edit_piece'):
        piece_a_modifier = Piece.objects.filter(ref_piece=request.GET['edit_piece']).first()

    achat_a_modifier = None
    if request.GET.get('edit_achat'):
        achat_a_modifier = AchatPiece.objects.filter(id_achat=request.GET['edit_achat']).first()

    fournisseur_a_modifier = None
    if request.GET.get('edit_fournisseur'):
        fournisseur_a_modifier = Fournisseur.objects.filter(
            code_fournisseur=request.GET['edit_fournisseur']
        ).first()

    total_pieces_stock = Piece.objects.aggregate(
        total=Coalesce(Sum('qte_stock'), 0)
    )['total']

    return render(request, 'usine/espace_stocks.html', {
        'role': _groupe_principal(request.user),
        'pieces': Piece.objects.all().order_by('ref_piece'),
        'fournisseurs': Fournisseur.objects.all().order_by('code_fournisseur'),
        'achats': AchatPiece.objects.select_related('ref_piece', 'code_fournisseur').order_by('-id_achat'),
        'piece_a_modifier': piece_a_modifier,
        'achat_a_modifier': achat_a_modifier,
        'fournisseur_a_modifier': fournisseur_a_modifier,
        'total_pieces_stock': total_pieces_stock,
        'erreur': erreur,
        'succes': succes,
    })
# ==========================================
# 2. GESTION DE LA MAINTENANCE
# ==========================================
def _assurer_machine_existe(id_machine):
    machine_id = int(id_machine)
    code_mach = f"MACH-{machine_id}"
    designation_mach = f"Machine {machine_id}"
    num_ligne_defaut = 'L01'
    with connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO machine (id_machine, code_machine, designation, num_ligne)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (id_machine) DO NOTHING
            """,
            [machine_id, code_mach, designation_mach, num_ligne_defaut],
        )
    return machine_id


@login_required
def espace_maintenance(request):
    erreur = None
    succes = request.session.pop('succes_maint', None)
    erreur_session = request.session.pop('erreur_maint', None)
    if erreur_session:
        erreur = erreur_session

    if request.method == 'POST':
        action = request.POST.get('action')
        try:
            if action == 'maintenance':
                minutes = int(request.POST['duree_minutes'])
                date_debut = request.POST.get('date_heure_debut')
                dt = datetime.fromisoformat(date_debut) if date_debut else timezone.now()
                if timezone.is_naive(dt):
                    dt = timezone.make_aware(dt)

                machine_id = _assurer_machine_existe(request.POST['id_machine'])
                maint = Maintenance.objects.create(
                    date_heure_debut=dt,
                    duree=timedelta(minutes=minutes),
                    id_machine=machine_id,
                )

                ref_piece = request.POST.get('ref_piece')
                qte_consommee = int(request.POST.get('quantite_consommee') or 0)
                if ref_piece and qte_consommee > 0:
                    piece = get_object_or_404(Piece, ref_piece=ref_piece)
                    if piece.qte_stock < qte_consommee:
                        raise ValueError(
                            f"Stock insuffisant pour {piece.ref_piece} (disponible : {piece.qte_stock})."
                        )

                    with connection.cursor() as cursor:
                        cursor.execute(
                            """
                            INSERT INTO consommer_piece (id_maintenance, ref_piece, quantite_consommee)
                            VALUES (%s, %s, %s)
                            ON CONFLICT (id_maintenance, ref_piece)
                            DO UPDATE SET quantite_consommee = consommer_piece.quantite_consommee + EXCLUDED.quantite_consommee
                            """,
                            [maint.id_maintenance, piece.ref_piece, qte_consommee],
                        )

                    piece.qte_stock -= qte_consommee
                    piece.save(update_fields=['qte_stock'])

                request.session['succes_maint'] = "Intervention de maintenance enregistrée."

            elif action == 'modifier_maintenance':
                maint = get_object_or_404(Maintenance, id_maintenance=request.POST['id_maintenance'])
                maint.id_machine = _assurer_machine_existe(request.POST['id_machine'])
                maint.duree = timedelta(minutes=int(request.POST['duree_minutes']))
                if request.POST.get('date_heure_debut'):
                    dt = datetime.fromisoformat(request.POST['date_heure_debut'])
                    if timezone.is_naive(dt):
                        dt = timezone.make_aware(dt)
                    maint.date_heure_debut = dt
                maint.save()
                request.session['succes_maint'] = f"Maintenance #{maint.id_maintenance} modifiée."

            elif action == 'supprimer_maintenance':
                maint = get_object_or_404(Maintenance, id_maintenance=request.POST['id_maintenance'])
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        SELECT ref_piece, quantite_consommee
                        FROM consommer_piece
                        WHERE id_maintenance = %s
                        """,
                        [maint.id_maintenance],
                    )
                    lignes_conso = cursor.fetchall()
                    for ref_p, qte_c in lignes_conso:
                        Piece.objects.filter(ref_piece=ref_p).update(
                            qte_stock=F('qte_stock') + qte_c
                        )
                    cursor.execute(
                        "DELETE FROM consommer_piece WHERE id_maintenance = %s",
                        [maint.id_maintenance],
                    )
                maint.delete()
                request.session['succes_maint'] = f"Maintenance #{maint.id_maintenance} supprimée."

            return redirect('espace_maintenance')
        except Exception as e:
            request.session['erreur_maint'] = str(e)
            return redirect('espace_maintenance')

    maint_a_modifier = None
    duree_minutes_edit = ''
    if request.GET.get('edit_maint'):
        maint_a_modifier = Maintenance.objects.filter(id_maintenance=request.GET['edit_maint']).first()
        if maint_a_modifier:
            duree_minutes_edit = _minutes_depuis_duree(maint_a_modifier.duree)

    total_pieces_stock = Piece.objects.aggregate(
        total=Coalesce(Sum('qte_stock'), 0)
    )['total']

    with connection.cursor() as cursor:
        cursor.execute("SELECT id_machine, code_machine, designation FROM machine ORDER BY id_machine")
        colonnes = [col[0] for col in cursor.description]
        machines_liste = [dict(zip(colonnes, row)) for row in cursor.fetchall()]

    return render(request, 'usine/espace_maintenance.html', {
        'role': _groupe_principal(request.user),
        'pieces': Piece.objects.all().order_by('ref_piece'),
        'machines': machines_liste,
        'maintenances': Maintenance.objects.order_by('-id_maintenance'),
        'consommations': ConsommerPiece.objects.select_related('id_maintenance', 'ref_piece').order_by('-id_maintenance'),
        'maint_a_modifier': maint_a_modifier,
        'duree_minutes_edit': duree_minutes_edit,
        'total_pieces_stock': total_pieces_stock,
        'erreur': erreur,
        'succes': succes,
    })

# ==========================================
# 3. GESTION DES INCIDENTS (RESPONSABLE)
# ==========================================
def _obtenir_ou_creer_type_incident(libelle_saisi):
    libelle_propre = (libelle_saisi or '').strip()
    if not libelle_propre:
        libelle_propre = "Incident non spécifié"
    existant = TypeIncident.objects.filter(libelle__iexact=libelle_propre).first()
    if existant:
        return existant
    code = f"TY{uuid.uuid4().hex[:8].upper()}"
    return TypeIncident.objects.create(code_type=code, libelle=libelle_propre)


def _assurer_lot_existe(id_lot):
    lot_id = int(id_lot)
    ref_prod = 'STANDARD'
    with connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO produit (ref_produit, designation, prix_vente_unitaire)
            VALUES (%s, %s, %s)
            ON CONFLICT (ref_produit) DO NOTHING
            """,
            [ref_prod, 'Produit standard', 0],
        )
        cursor.execute(
            """
            INSERT INTO lot_production (id_lot, num_ligne, ref_produit)
            VALUES (%s, %s, %s)
            ON CONFLICT (id_lot) DO NOTHING
            """,
            [lot_id, 'L01', ref_prod],
        )
    return lot_id


@login_required
def espace_responsable(request):
    erreur = None
    succes = request.session.pop('succes_resp', None)
    erreur_session = request.session.pop('erreur_resp', None)
    if erreur_session:
        erreur = erreur_session

    if request.method == 'POST':
        action = request.POST.get('action')
        try:
            if action == 'incident':
                num_saisi = request.POST.get('num_incident', '').strip()
                if not num_saisi:
                    num_saisi = f"INC-{timezone.now().strftime('%H%M%S')}-{uuid.uuid4().hex[:4].upper()}"
                minutes = int(request.POST['temps_arret_minutes'])
                lot_id = _assurer_lot_existe(request.POST['id_lot'])
                type_inc = _obtenir_ou_creer_type_incident(request.POST.get('raison_incident'))
                Incident.objects.create(
                    num_incident=num_saisi,
                    temps_arret=timedelta(minutes=minutes),
                    id_lot=lot_id,
                    code_type=type_inc,
                )
                request.session['succes_resp'] = f"Incident {num_saisi} enregistré (Lot {lot_id})."

            elif action == 'modifier_incident':
                inc = get_object_or_404(Incident, num_incident=request.POST['num_incident'])
                inc.id_lot = _assurer_lot_existe(request.POST['id_lot'])
                inc.code_type = _obtenir_ou_creer_type_incident(request.POST.get('raison_incident'))
                inc.temps_arret = timedelta(minutes=int(request.POST['temps_arret_minutes']))
                inc.save()
                request.session['succes_resp'] = f"Incident {inc.num_incident} modifié."

            elif action == 'supprimer_incident':
                inc = get_object_or_404(Incident, num_incident=request.POST['num_incident'])
                inc.delete()
                request.session['succes_resp'] = f"Incident {inc.num_incident} supprimé."

            return redirect('espace_responsable')
        except Exception as e:
            request.session['erreur_resp'] = str(e)
            return redirect('espace_responsable')

    incident_a_modifier = None
    arret_minutes_edit = ''
    if request.GET.get('edit_incident'):
        incident_a_modifier = Incident.objects.filter(num_incident=request.GET['edit_incident']).first()
        if incident_a_modifier:
            arret_minutes_edit = _minutes_depuis_duree(incident_a_modifier.temps_arret)

    return render(request, 'usine/espace_responsable.html', {
        'role': _groupe_principal(request.user),
        'types_incident': TypeIncident.objects.all().order_by('libelle'),
        'incidents': Incident.objects.select_related('code_type').order_by('-num_incident'),
        'incident_a_modifier': incident_a_modifier,
        'arret_minutes_edit': arret_minutes_edit,
        'erreur': erreur,
        'succes': succes,
    })