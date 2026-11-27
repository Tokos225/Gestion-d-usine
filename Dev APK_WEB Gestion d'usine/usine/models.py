from django.db import models

# Create your models here.

from django.db import models


class Fournisseur(models.Model):
    code_fournisseur = models.CharField(max_length=20, primary_key=True)
    raison_sociale = models.CharField(max_length=120)
    adresse = models.TextField(blank=True, null=True)
    telephone = models.CharField(max_length=30, blank=True, null=True)

    class Meta:
        db_table = 'fournisseur'
        managed = False

    def __str__(self):
        return f"{self.code_fournisseur} - {self.raison_sociale}"


class Piece(models.Model):
    ref_piece = models.CharField(max_length=30, primary_key=True)
    libelle = models.CharField(max_length=120)
    prix_unitaire_ht = models.DecimalField(max_digits=12, decimal_places=2)
    qte_stock = models.IntegerField()

    class Meta:
        db_table = 'piece'
        managed = False

    def __str__(self):
        return f"{self.ref_piece} - {self.libelle} (Stock: {self.qte_stock})"


class AchatPiece(models.Model):
    id_achat = models.AutoField(primary_key=True)
    ref_piece = models.ForeignKey(Piece, models.DO_NOTHING, db_column='ref_piece')
    code_fournisseur = models.ForeignKey(Fournisseur, models.DO_NOTHING, db_column='code_fournisseur')
    prix_achat = models.DecimalField(max_digits=12, decimal_places=2)
    date_achat = models.DateField()
    quantite_achetee = models.IntegerField()

    class Meta:
        db_table = 'achat_piece'
        managed = False


class Nomenclature(models.Model):
    ref_piece_composee = models.ForeignKey(
        Piece, models.DO_NOTHING, db_column='ref_piece_composee', related_name='composantes'
    )
    ref_piece_composante = models.ForeignKey(
        Piece, models.DO_NOTHING, db_column='ref_piece_composante', related_name='composees'
    )
    quantite_exemplaires = models.IntegerField()

    class Meta:
        db_table = 'nomenclature'
        managed = False
        unique_together = (('ref_piece_composee', 'ref_piece_composante'),)


class TypeIncident(models.Model):
    code_type = models.CharField(max_length=20, primary_key=True)
    libelle = models.CharField(max_length=120)

    class Meta:
        db_table = 'type_incident'
        managed = False

    def __str__(self):
        return f"{self.code_type} - {self.libelle}"


class Incident(models.Model):
    num_incident = models.CharField(max_length=30, primary_key=True)
    temps_arret = models.DurationField()
    id_lot = models.IntegerField()
    code_type = models.ForeignKey(TypeIncident, models.DO_NOTHING, db_column='code_type')

    class Meta:
        db_table = 'incident'
        managed = False


class Maintenance(models.Model):
    id_maintenance = models.AutoField(primary_key=True)
    date_heure_debut = models.DateTimeField()
    duree = models.DurationField()
    id_machine = models.IntegerField()

    class Meta:
        db_table = 'maintenance'
        managed = False


class ConsommerPiece(models.Model):
    id_maintenance = models.ForeignKey(Maintenance, models.DO_NOTHING, db_column='id_maintenance')
    ref_piece = models.ForeignKey(Piece, models.DO_NOTHING, db_column='ref_piece')
    quantite_consommee = models.IntegerField()

    class Meta:
        db_table = 'consommer_piece'
        managed = False
        unique_together = (('id_maintenance', 'ref_piece'),)