"""Paquet du projet « prévision du risque et allocation d'un portefeuille actions-obligations ».

Le projet suit la démarche du cours (Course 6, Introduction to Machine Learning) :
1. définition du problème ; 2. exploration ; 3. prétraitement ; 4. construction des
variables ; 5. modélisation ; 6. évaluation ; 7. interprétation.

Architecture ::

    portefeuille/
        config.py          chemins, calendrier NYSE et toutes les hypothèses du protocole
        utilitaires.py     écritures de fichiers sûres et empreintes SHA-256
        collecte/          téléchargement et traçabilité des 29 sources brutes
        pretraitement/     étape 3 : lecture, validation et alignement de chaque source
        features/          étape 4 : variables historiques A, cible, indicateurs implicites B
        controles/         couverture du calendrier, émetteurs, qualité de la surface
        controle_surface/  vérification de la surface par les vrais contrats de 2022, prix à terme

Les scripts de ``scripts/`` enchaînent ces fonctions dans l'ordre d'exécution.
"""
