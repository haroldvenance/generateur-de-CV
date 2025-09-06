import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, filedialog, PhotoImage, simpledialog
import sqlite3
import hashlib
import os
import datetime
import json
import base64
import tempfile
import shutil
from tkinter import font as tkfont
from PIL import Image, ImageTk, ImageOps
import threading
import webbrowser
from fpdf import FPDF
import html

class CVGeneratorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("📄 Plateforme de Génération de CV")
        self.root.geometry("1200x800")
        self.root.configure(bg='#f5f6fa')

        # Fichier de base de données
        self.db_file = "cv_platform.db"

        # Attributs utilisateur / CV
        self.current_user = None
        self.current_cv_id = None
        self.current_template = "classic"
        self.photo_path = None

        # Données d'édition (structures en mémoire)
        self.experience_data = []   # liste de dicts
        self.education_data = []    # liste de dicts
        self.skills_data = []       # liste de str ou dict
        self.languages_data = []    # liste de dicts

        # Mapping entre Listbox indices et IDs en base
        self.cv_ids = []

        # Index en cours d'édition pour expérience / education / languages
        self.editing_experience_index = None
        self.editing_education_index = None
        self.editing_language_index = None

        # Templates disponibles
        self.templates = {
            "classic": "Classique",
            "modern": "Moderne",
            "creative": "Créatif",
            "professional": "Professionnel"
        }

        # Compétences prédéfinies (initialisation)
        self.predefined_skills = [
            "Python", "JavaScript", "Java", "C++", "PHP", "SQL", "HTML/CSS",
            "React", "Angular", "Vue.js", "Node.js", "Django", "Flask",
            "Git", "Docker", "AWS", "Azure", "Machine Learning",
            "Data Analysis", "Project Management", "Agile/Scrum",
            "Communication", "Leadership", "Problem Solving"
        ]

        # Créer dossiers utiles
        self.create_folders()

        # Polices
        self.setup_fonts()

        # Connexion DB + tables
        self.init_db()

        # Interface (onglets, frames, widgets)
        self.setup_interface()

        # Charger liste de compétences dans skills_listbox si existant
        # (sera généré quand connecte)
        # lancement autosave
        self.setup_autosave()

    # -----------------------
    # Utilitaires init
    # -----------------------
    def create_folders(self):
        """Crée les dossiers nécessaires"""
        folders = ["uploads", "exports", "templates", "backups"]
        for folder in folders:
            os.makedirs(folder, exist_ok=True)

    def setup_fonts(self):
        """Configure les polices"""
        self.title_font = tkfont.Font(family="Arial", size=20, weight="bold")
        self.subtitle_font = tkfont.Font(family="Arial", size=14, weight="bold")
        self.normal_font = tkfont.Font(family="Arial", size=10)
        self.small_font = tkfont.Font(family="Arial", size=8)

    def hash_password(self, password):
        """Hash un mot de passe avec SHA-256"""
        return hashlib.sha256(password.encode()).hexdigest()

    # -----------------------
    # Base de données
    # -----------------------
    def init_db(self):
        """Initialise la base de données SQLite"""
        try:
            self.conn = sqlite3.connect(self.db_file, check_same_thread=False)
            self.cursor = self.conn.cursor()

            # Table utilisateurs
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    email TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    first_name TEXT NOT NULL,
                    last_name TEXT NOT NULL,
                    role TEXT DEFAULT 'candidate',
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    last_login DATETIME,
                    is_active BOOLEAN DEFAULT 1
                )
            ''')

            # Table CVs
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS cvs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    title TEXT NOT NULL,
                    template TEXT DEFAULT 'classic',
                    data TEXT NOT NULL,
                    photo_path TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    is_public BOOLEAN DEFAULT 0,
                    view_count INTEGER DEFAULT 0,
                    FOREIGN KEY (user_id) REFERENCES users (id)
                )
            ''')

            # Table compétences
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS skills (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    category TEXT,
                    description TEXT
                )
            ''')

            # Table compétences utilisateur
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS user_skills (
                    user_id INTEGER NOT NULL,
                    skill_id INTEGER NOT NULL,
                    level INTEGER DEFAULT 1,
                    experience_years INTEGER DEFAULT 0,
                    last_used INTEGER,
                    PRIMARY KEY (user_id, skill_id),
                    FOREIGN KEY (user_id) REFERENCES users (id),
                    FOREIGN KEY (skill_id) REFERENCES skills (id)
                )
            ''')

            # Table historique CV
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS cv_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    cv_id INTEGER NOT NULL,
                    data TEXT NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (cv_id) REFERENCES cvs (id)
                )
            ''')

            # Table vues CV
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS cv_views (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    cv_id INTEGER NOT NULL,
                    viewer_id INTEGER,
                    viewed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    ip_address TEXT,
                    FOREIGN KEY (cv_id) REFERENCES cvs (id),
                    FOREIGN KEY (viewer_id) REFERENCES users (id)
                )
            ''')

            # Insérer compétences prédéfinies
            for skill in self.predefined_skills:
                try:
                    self.cursor.execute('INSERT OR IGNORE INTO skills (name) VALUES (?)', (skill,))
                except sqlite3.Error:
                    pass

            self.conn.commit()

        except sqlite3.Error as e:
            messagebox.showerror("Erreur BD", f"Erreur initialisation: {e}")
            raise

    # -----------------------
    # Interface principale
    # -----------------------
    def setup_interface(self):
        """Configure l'interface principale"""
        # Style
        style = ttk.Style()
        style.configure('TFrame', background='#f5f6fa')
        style.configure('TLabel', background='#f5f6fa')
        style.configure('TButton', background='#3498db', foreground='white')

        # Notebook pour les onglets
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Onglets
        self.login_tab = ttk.Frame(self.notebook)
        self.register_tab = ttk.Frame(self.notebook)
        self.dashboard_tab = ttk.Frame(self.notebook)
        self.editor_tab = ttk.Frame(self.notebook)
        self.skills_tab = ttk.Frame(self.notebook)

        self.notebook.add(self.login_tab, text="Connexion")
        self.notebook.add(self.register_tab, text="Inscription")
        self.notebook.add(self.dashboard_tab, text="Tableau de bord", state='hidden')
        self.notebook.add(self.editor_tab, text="Éditeur CV", state='hidden')
        self.notebook.add(self.skills_tab, text="Compétences", state='hidden')

        # Setup each tab
        self.setup_login_tab()
        self.setup_register_tab()
        self.setup_dashboard_tab()
        self.setup_editor_tab()
        self.setup_skills_tab()

        # Afficher l'onglet de connexion par défaut
        self.notebook.select(0)

    # -----------------------
    # Login / Register Tabs
    # -----------------------
    def setup_login_tab(self):
        """Configure l'onglet de connexion"""
        frame = tk.Frame(self.login_tab, bg='#ffffff', padx=30, pady=30)
        frame.pack(expand=True, fill=tk.BOTH)

        tk.Label(frame, text="🔐 Connexion", font=self.title_font, bg='#ffffff').pack(pady=20)

        # Formulaire
        form_frame = tk.Frame(frame, bg='#ffffff')
        form_frame.pack(pady=20)

        tk.Label(form_frame, text="Email:", bg='#ffffff').grid(row=0, column=0, sticky='e', pady=5, padx=5)
        self.login_email = tk.Entry(form_frame, width=30)
        self.login_email.grid(row=0, column=1, pady=5, padx=5)

        tk.Label(form_frame, text="Mot de passe:", bg='#ffffff').grid(row=1, column=0, sticky='e', pady=5, padx=5)
        self.login_password = tk.Entry(form_frame, show="•", width=30)
        self.login_password.grid(row=1, column=1, pady=5, padx=5)

        # Boutons
        btn_frame = tk.Frame(frame, bg='#ffffff')
        btn_frame.pack(pady=20)

        tk.Button(btn_frame, text="Se connecter", command=self.login,
                 bg='#3498db', fg='white', padx=20).pack(side=tk.LEFT, padx=10)
        tk.Button(btn_frame, text="Mot de passe oublié", command=self.forgot_password,
                 bg='#95a5a6', fg='white').pack(side=tk.LEFT, padx=10)

    def setup_register_tab(self):
        """Configure l'onglet d'inscription"""
        frame = tk.Frame(self.register_tab, bg='#ffffff', padx=30, pady=30)
        frame.pack(expand=True, fill=tk.BOTH)

        tk.Label(frame, text="👤 Créer un compte", font=self.title_font, bg='#ffffff').pack(pady=20)

        # Formulaire
        form_frame = tk.Frame(frame, bg='#ffffff')
        form_frame.pack(pady=20)

        fields = [
            ("Prénom:", "register_first_name"),
            ("Nom:", "register_last_name"),
            ("Email:", "register_email"),
            ("Mot de passe:", "register_password"),
            ("Confirmer:", "register_confirm")
        ]

        self.register_vars = {}
        for i, (label, var_name) in enumerate(fields):
            tk.Label(form_frame, text=label, bg='#ffffff').grid(row=i, column=0, sticky='e', pady=5, padx=5)
            var = tk.StringVar()
            entry = tk.Entry(form_frame, textvariable=var, width=30)
            if "password" in var_name or "confirm" in var_name:
                entry.config(show="•")
            entry.grid(row=i, column=1, pady=5, padx=5)
            self.register_vars[var_name] = var

        # Rôle
        tk.Label(form_frame, text="Rôle:", bg='#ffffff').grid(row=5, column=0, sticky='e', pady=5, padx=5)
        self.register_role = ttk.Combobox(form_frame, values=["candidat", "recruteur"], state="readonly", width=27)
        self.register_role.set("candidat")
        self.register_role.grid(row=5, column=1, pady=5, padx=5)

        # Bouton
        tk.Button(frame, text="Créer mon compte", command=self.register,
                 bg='#27ae60', fg='white', padx=20, pady=5).pack(pady=20)

    # -----------------------
    # Dashboard Tab
    # -----------------------
    def setup_dashboard_tab(self):
        """Configure le tableau de bord"""
        # Header
        header_frame = tk.Frame(self.dashboard_tab, bg='#2c3e50', height=60)
        header_frame.pack(fill=tk.X)
        header_frame.pack_propagate(False)

        tk.Label(header_frame, text="📊 Tableau de bord", font=self.title_font,
                 bg='#2c3e50', fg='white').pack(side=tk.LEFT, padx=20)

        # User info
        self.user_info_frame = tk.Frame(header_frame, bg='#2c3e50')
        self.user_info_frame.pack(side=tk.RIGHT, padx=20)

        # Content
        content_frame = tk.Frame(self.dashboard_tab, bg='#f5f6fa')
        content_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        # Left panel - CV list
        left_frame = tk.Frame(content_frame, bg='#ffffff', width=300)
        left_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))
        left_frame.pack_propagate(False)

        tk.Label(left_frame, text="Mes CVs", font=self.subtitle_font, bg='#ffffff').pack(pady=10)

        # Listbox for CVs
        self.cv_listbox = tk.Listbox(left_frame, font=self.normal_font)
        self.cv_listbox.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        self.cv_listbox.bind('<<ListboxSelect>>', self.on_cv_select)

        # CV actions
        cv_btn_frame = tk.Frame(left_frame, bg='#ffffff')
        cv_btn_frame.pack(fill=tk.X, pady=5)

        tk.Button(cv_btn_frame, text="Nouveau CV", command=self.new_cv,
                 bg='#3498db', fg='white').pack(side=tk.LEFT, padx=2)
        tk.Button(cv_btn_frame, text="Supprimer", command=self.delete_cv,
                 bg='#e74c3c', fg='white').pack(side=tk.LEFT, padx=2)

        # Right panel - CV preview and stats
        right_frame = tk.Frame(content_frame, bg='#ffffff')
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        # Preview
        tk.Label(right_frame, text="Aperçu", font=self.subtitle_font, bg='#ffffff').pack(pady=10)

        self.preview_frame = tk.Frame(right_frame, bg='#ecf0f1', height=400)
        self.preview_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # Stats
        stats_frame = tk.Frame(right_frame, bg='#ffffff')
        stats_frame.pack(fill=tk.X, pady=10)

        tk.Label(stats_frame, text="Statistiques:", font=self.subtitle_font, bg='#ffffff').pack(anchor='w')

        self.stats_label = tk.Label(stats_frame, text="Sélectionnez un CV pour voir les statistiques",
                                    bg='#ffffff', justify=tk.LEFT)
        self.stats_label.pack(anchor='w', padx=10)

    # -----------------------
    # Editor Tab
    # -----------------------
    def setup_editor_tab(self):
        """Configure l'éditeur de CV"""
        # Header avec sauvegarde
        header_frame = tk.Frame(self.editor_tab, bg='#34495e', height=50)
        header_frame.pack(fill=tk.X)
        header_frame.pack_propagate(False)

        tk.Label(header_frame, text="✏️ Éditeur de CV", font=self.subtitle_font,
                 bg='#34495e', fg='white').pack(side=tk.LEFT, padx=20)

        # Template selection
        template_frame = tk.Frame(header_frame, bg='#34495e')
        template_frame.pack(side=tk.LEFT, padx=20)

        tk.Label(template_frame, text="Template:", bg='#34495e', fg='white').pack(side=tk.LEFT)
        self.template_var = tk.StringVar(value="classic")
        template_combo = ttk.Combobox(template_frame, textvariable=self.template_var,
                                      values=list(self.templates.keys()), state="readonly", width=15)
        template_combo.pack(side=tk.LEFT, padx=5)
        template_combo.bind('<<ComboboxSelected>>', self.change_template)

        # Save buttons
        save_frame = tk.Frame(header_frame, bg='#34495e')
        save_frame.pack(side=tk.RIGHT, padx=20)

        tk.Button(save_frame, text="💾 Sauvegarder", command=self.save_cv,
                 bg='#27ae60', fg='white').pack(side=tk.LEFT, padx=5)
        tk.Button(save_frame, text="📤 Exporter PDF", command=self.export_pdf,
                 bg='#e67e22', fg='white').pack(side=tk.LEFT, padx=5)
        tk.Button(save_frame, text="📋 Exporter Word", command=self.export_word,
                 bg='#3498db', fg='white').pack(side=tk.LEFT, padx=5)

        # Main content
        main_frame = tk.Frame(self.editor_tab, bg='#f5f6fa')
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Left panel - Form
        form_frame = tk.Frame(main_frame, bg='#ffffff', width=400)
        form_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))
        form_frame.pack_propagate(False)

        # Notebook for sections
        self.sections_notebook = ttk.Notebook(form_frame)
        self.sections_notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Sections
        self.setup_personal_section()
        self.setup_experience_section()
        self.setup_education_section()
        self.setup_skills_section_editor()
        self.setup_languages_section()

        # Right panel - Live preview
        preview_frame = tk.Frame(main_frame, bg='#ffffff')
        preview_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        tk.Label(preview_frame, text="Aperçu en direct", font=self.subtitle_font, bg='#ffffff').pack(pady=10)

        self.preview_canvas = tk.Canvas(preview_frame, bg='white', relief=tk.SUNKEN, bd=1)
        self.preview_canvas.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

    def setup_personal_section(self):
        """Configure la section informations personnelles"""
        frame = ttk.Frame(self.sections_notebook)
        self.sections_notebook.add(frame, text="Personnel")

        # Photo upload
        photo_frame = tk.Frame(frame, bg='#ffffff')
        photo_frame.pack(fill=tk.X, pady=10)

        self.photo_label = tk.Label(photo_frame, text="📷 Aucune photo", bg='#ffffff')
        self.photo_label.pack()

        tk.Button(photo_frame, text="Uploader photo", command=self.upload_photo,
                 bg='#3498db', fg='white').pack(pady=5)

        # Personal info
        personal_frame = tk.Frame(frame, bg='#ffffff')
        personal_frame.pack(fill=tk.BOTH, expand=True)

        fields = [
            ("Prénom*:", "personal_first_name"),
            ("Nom*:", "personal_last_name"),
            ("Titre:", "personal_title"),
            ("Email*:", "personal_email"),
            ("Téléphone:", "personal_phone"),
            ("Adresse:", "personal_address"),
            ("LinkedIn:", "personal_linkedin"),
            ("Site web:", "personal_website")
        ]

        self.personal_vars = {}
        for i, (label, var_name) in enumerate(fields):
            tk.Label(personal_frame, text=label, bg='#ffffff').grid(row=i, column=0, sticky='e', pady=2, padx=5)
            var = tk.StringVar()
            entry = tk.Entry(personal_frame, textvariable=var, width=30)
            entry.grid(row=i, column=1, pady=2, padx=5)
            entry.bind('<KeyRelease>', self.update_preview)
            self.personal_vars[var_name] = var

        # Description
        tk.Label(personal_frame, text="Description:", bg='#ffffff').grid(row=len(fields), column=0, sticky='ne', pady=2, padx=5)
        self.personal_description = scrolledtext.ScrolledText(personal_frame, width=30, height=5)
        self.personal_description.grid(row=len(fields), column=1, pady=2, padx=5)
        self.personal_description.bind('<KeyRelease>', self.update_preview)

    # -----------------------
    # Experience Section (full)
    # -----------------------
    def setup_experience_section(self):
        """Configure la section expérience professionnelle"""
        frame = ttk.Frame(self.sections_notebook)
        self.sections_notebook.add(frame, text="Expérience")

        # Experience list and buttons
        exp_frame = tk.Frame(frame, bg='#ffffff')
        exp_frame.pack(fill=tk.BOTH, expand=True)

        left_list_frame = tk.Frame(exp_frame, bg='#ffffff')
        left_list_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0,5))

        self.experience_listbox = tk.Listbox(left_list_frame, height=10)
        self.experience_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
        self.experience_listbox.bind('<<ListboxSelect>>', self.on_experience_select)

        # Buttons
        btn_frame = tk.Frame(left_list_frame, bg='#ffffff')
        btn_frame.pack(side=tk.RIGHT, fill=tk.Y)
        tk.Button(btn_frame, text="➕", command=self.add_experience, width=3).pack(pady=2)
        tk.Button(btn_frame, text="✏️", command=self.edit_experience, width=3).pack(pady=2)
        tk.Button(btn_frame, text="🗑️", command=self.delete_experience, width=3).pack(pady=2)

        # Form for editing
        self.experience_form_frame = tk.Frame(frame, bg='#ffffff')
        self.experience_form_frame.pack(fill=tk.X, pady=10)

        exp_fields = [
            ("Poste*:", "exp_position"),
            ("Entreprise*:", "exp_company"),
            ("Lieu:", "exp_location"),
            ("Date début*:", "exp_start_date"),
            ("Date fin:", "exp_end_date"),
            ("En cours:", "exp_current")
        ]

        self.experience_vars = {}
        # layout 2 columns
        for i, (label, var_name) in enumerate(exp_fields):
            row = i // 2
            col = (i % 2) * 2
            tk.Label(self.experience_form_frame, text=label, bg='#ffffff').grid(row=row, column=col, sticky='e', pady=2, padx=5)
            if var_name == "exp_current":
                var = tk.BooleanVar()
                check = tk.Checkbutton(self.experience_form_frame, variable=var, bg='#ffffff', command=self.on_experience_current_toggle)
                check.grid(row=row, column=col+1, sticky='w', pady=2, padx=5)
            else:
                var = tk.StringVar()
                entry = tk.Entry(self.experience_form_frame, textvariable=var, width=20)
                entry.grid(row=row, column=col+1, pady=2, padx=5)
                entry.bind('<KeyRelease>', lambda e: self.update_preview())
            self.experience_vars[var_name] = var

        # Description
        tk.Label(self.experience_form_frame, text="Description:", bg='#ffffff').grid(row=3, column=0, sticky='ne', pady=2, padx=5)
        self.experience_description = scrolledtext.ScrolledText(self.experience_form_frame, width=40, height=4)
        self.experience_description.grid(row=3, column=1, columnspan=3, pady=2, padx=5, sticky='ew')
        self.experience_description.bind('<KeyRelease>', lambda e: self.update_preview())

        # Save button
        tk.Button(self.experience_form_frame, text="💾 Sauvegarder", command=self.save_experience,
                 bg='#27ae60', fg='white').grid(row=4, column=1, columnspan=2, pady=10)

    def on_experience_current_toggle(self):
        """Désactive la date de fin si 'En cours' est coché"""
        if self.experience_vars.get('exp_current') and self.experience_vars['exp_current'].get():
            self.experience_vars['exp_end_date'].set('')
        self.update_preview()

    def add_experience(self):
        """Prépare le formulaire pour ajouter une expérience"""
        self.clear_experience_form()
        self.editing_experience_index = None
        self.sections_notebook.select(1)  # garder onglet expérience ouvert

    def edit_experience(self):
        """Charge une expérience sélectionnée dans le formulaire pour édition"""
        sel = self.experience_listbox.curselection()
        if not sel:
            messagebox.showwarning("Attention", "Sélectionnez une expérience à modifier")
            return
        idx = sel[0]
        exp = self.experience_data[idx]
        self.editing_experience_index = idx
        # Remplir le formulaire
        self.experience_vars['exp_position'].set(exp.get('position', ''))
        self.experience_vars['exp_company'].set(exp.get('company', ''))
        self.experience_vars['exp_location'].set(exp.get('location', ''))
        self.experience_vars['exp_start_date'].set(exp.get('start_date', ''))
        self.experience_vars['exp_end_date'].set(exp.get('end_date', ''))
        self.experience_vars['exp_current'].set(bool(exp.get('current', False)))
        self.experience_description.delete(1.0, tk.END)
        self.experience_description.insert(1.0, exp.get('description', ''))
        self.sections_notebook.select(1)

    def delete_experience(self):
        """Supprime l'expérience sélectionnée"""
        sel = self.experience_listbox.curselection()
        if not sel:
            messagebox.showwarning("Attention", "Sélectionnez une expérience à supprimer")
            return
        idx = sel[0]
        if messagebox.askyesno("Confirmation", "Supprimer cette expérience ?"):
            del self.experience_data[idx]
            self.refresh_experience_list()
            self.update_preview()

    def on_experience_select(self, event=None):
        """Affiche un aperçu rapide de l'expérience sélectionnée"""
        sel = self.experience_listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        exp = self.experience_data[idx]
        # afficher description dans preview canvas ou dans un petit popup
        preview_text = f"{exp.get('position','')} - {exp.get('company','')}\n{exp.get('start_date','')} - {exp.get('end_date','') if not exp.get('current') else 'Présent'}\n\n{exp.get('description','')[:300]}"
        # petite fenêtre info (non intrusive)
        self.preview_canvas.delete("all")
        self.preview_canvas.create_text(10, 10, anchor='nw', text=preview_text, font=("Arial", 10), fill="black")

    def save_experience(self):
        """Sauvegarde l'expérience en cours (ajout ou mise à jour)"""
        position = self.experience_vars['exp_position'].get().strip()
        company = self.experience_vars['exp_company'].get().strip()
        location = self.experience_vars['exp_location'].get().strip()
        start_date = self.experience_vars['exp_start_date'].get().strip()
        end_date = self.experience_vars['exp_end_date'].get().strip()
        current = bool(self.experience_vars['exp_current'].get())
        description = self.experience_description.get(1.0, tk.END).strip()

        if not position or not company or not start_date:
            messagebox.showerror("Erreur", "Veuillez remplir les champs obligatoires (Poste, Entreprise, Date début).")
            return

        entry = {
            "position": position,
            "company": company,
            "location": location,
            "start_date": start_date,
            "end_date": end_date,
            "current": current,
            "description": description
        }

        if self.editing_experience_index is None:
            # ajouter
            self.experience_data.insert(0, entry)
        else:
            # mise à jour
            self.experience_data[self.editing_experience_index] = entry
            self.editing_experience_index = None

        self.refresh_experience_list()
        self.clear_experience_form()
        self.update_preview()
        messagebox.showinfo("Succès", "Expérience sauvegardée")

    def refresh_experience_list(self):
        """Met à jour la listbox d'expériences"""
        self.experience_listbox.delete(0, tk.END)
        for exp in self.experience_data:
            label = f"{exp.get('position','')} - {exp.get('company','')} ({exp.get('start_date','')}{' - Présent' if exp.get('current') else (' - ' + (exp.get('end_date','') or ''))})"
            self.experience_listbox.insert(tk.END, label)

    def clear_experience_form(self):
        """Réinitialise le formulaire d'expérience"""
        for k, v in self.experience_vars.items():
            if isinstance(v, tk.BooleanVar):
                v.set(False)
            else:
                v.set('')
        self.experience_description.delete(1.0, tk.END)

    # -----------------------
    # Education Section
    # -----------------------
    def setup_education_section(self):
        """Configure la section formation"""
        frame = ttk.Frame(self.sections_notebook)
        self.sections_notebook.add(frame, text="Formation")

        # Listbox
        ed_frame = tk.Frame(frame, bg='#ffffff')
        ed_frame.pack(fill=tk.BOTH, expand=True)

        self.education_listbox = tk.Listbox(ed_frame, height=8)
        self.education_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0,5))
        self.education_listbox.bind('<<ListboxSelect>>', self.on_education_select)

        ed_btn_frame = tk.Frame(ed_frame, bg='#ffffff')
        ed_btn_frame.pack(side=tk.RIGHT, fill=tk.Y)
        tk.Button(ed_btn_frame, text="➕", command=self.add_education, width=3).pack(pady=2)
        tk.Button(ed_btn_frame, text="✏️", command=self.edit_education, width=3).pack(pady=2)
        tk.Button(ed_btn_frame, text="🗑️", command=self.delete_education, width=3).pack(pady=2)

        # Form
        self.education_form_frame = tk.Frame(frame, bg='#ffffff')
        self.education_form_frame.pack(fill=tk.X, pady=10)

        ed_fields = [
            ("Diplôme*:", "ed_degree"),
            ("Établissement*:", "ed_school"),
            ("Lieu:", "ed_location"),
            ("Année début*:", "ed_start_year"),
            ("Année fin:", "ed_end_year"),
            ("Description:", "ed_description")
        ]

        self.education_vars = {}
        for i, (label, var_name) in enumerate(ed_fields[:-1]):
            tk.Label(self.education_form_frame, text=label, bg='#ffffff').grid(row=i, column=0, sticky='e', pady=2, padx=5)
            var = tk.StringVar()
            entry = tk.Entry(self.education_form_frame, textvariable=var, width=30)
            entry.grid(row=i, column=1, pady=2, padx=5)
            entry.bind('<KeyRelease>', lambda e: self.update_preview())
            self.education_vars[var_name] = var

        tk.Label(self.education_form_frame, text="Description:", bg='#ffffff').grid(row=len(ed_fields)-1, column=0, sticky='ne', pady=2, padx=5)
        self.education_description = scrolledtext.ScrolledText(self.education_form_frame, width=40, height=4)
        self.education_description.grid(row=len(ed_fields)-1, column=1, pady=2, padx=5)

        tk.Button(self.education_form_frame, text="💾 Sauvegarder", command=self.save_education,
                 bg='#27ae60', fg='white').grid(row=len(ed_fields), column=1, pady=10)

    def add_education(self):
        self.clear_education_form()
        self.editing_education_index = None
        self.sections_notebook.select(2)

    def edit_education(self):
        sel = self.education_listbox.curselection()
        if not sel:
            messagebox.showwarning("Attention", "Sélectionnez une formation à modifier")
            return
        idx = sel[0]
        ed = self.education_data[idx]
        self.editing_education_index = idx
        self.education_vars['ed_degree'].set(ed.get('degree',''))
        self.education_vars['ed_school'].set(ed.get('school',''))
        self.education_vars['ed_location'].set(ed.get('location',''))
        self.education_vars['ed_start_year'].set(ed.get('start_year',''))
        self.education_vars['ed_end_year'].set(ed.get('end_year',''))
        self.education_description.delete(1.0, tk.END)
        self.education_description.insert(1.0, ed.get('description',''))
        self.sections_notebook.select(2)

    def delete_education(self):
        sel = self.education_listbox.curselection()
        if not sel:
            messagebox.showwarning("Attention", "Sélectionnez une formation à supprimer")
            return
        idx = sel[0]
        if messagebox.askyesno("Confirmation", "Supprimer cette formation ?"):
            del self.education_data[idx]
            self.refresh_education_list()
            self.update_preview()

    def save_education(self):
        degree = self.education_vars['ed_degree'].get().strip()
        school = self.education_vars['ed_school'].get().strip()
        start_year = self.education_vars['ed_start_year'].get().strip()

        if not degree or not school or not start_year:
            messagebox.showerror("Erreur", "Veuillez remplir les champs obligatoires (Diplôme, Établissement, Année début).")
            return

        entry = {
            "degree": degree,
            "school": school,
            "location": self.education_vars['ed_location'].get().strip(),
            "start_year": start_year,
            "end_year": self.education_vars['ed_end_year'].get().strip(),
            "description": self.education_description.get(1.0, tk.END).strip()
        }

        if self.editing_education_index is None:
            self.education_data.insert(0, entry)
        else:
            self.education_data[self.editing_education_index] = entry
            self.editing_education_index = None

        self.refresh_education_list()
        self.clear_education_form()
        self.update_preview()
        messagebox.showinfo("Succès", "Formation sauvegardée")

    def refresh_education_list(self):
        self.education_listbox.delete(0, tk.END)
        for ed in self.education_data:
            label = f"{ed.get('degree','')} - {ed.get('school','')} ({ed.get('start_year','')}{' - ' + ed.get('end_year','') if ed.get('end_year') else ''})"
            self.education_listbox.insert(tk.END, label)

    def clear_education_form(self):
        for v in self.education_vars.values():
            v.set('')
        self.education_description.delete(1.0, tk.END)

    def on_education_select(self, event=None):
        sel = self.education_listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        ed = self.education_data[idx]
        preview_text = f"{ed.get('degree','')} - {ed.get('school','')}\n{ed.get('start_year','')} - {ed.get('end_year','')}\n\n{ed.get('description','')[:300]}"
        self.preview_canvas.delete("all")
        self.preview_canvas.create_text(10, 10, anchor='nw', text=preview_text, font=("Arial", 10), fill="black")

    # -----------------------
    # Skills (editor tab)
    # -----------------------
    def setup_skills_section_editor(self):
        """Configure la section compétences dans l'éditeur"""
        frame = ttk.Frame(self.sections_notebook)
        self.sections_notebook.add(frame, text="Compétences")

        tk.Label(frame, text="Gérez vos compétences dans l'onglet 'Compétences'",
                 bg='#ffffff').pack(pady=50)

    # -----------------------
    # Languages Section
    # -----------------------
    def setup_languages_section(self):
        """Configure la section langues"""
        frame = ttk.Frame(self.sections_notebook)
        self.sections_notebook.add(frame, text="Langues")

        lang_frame = tk.Frame(frame, bg='#ffffff')
        lang_frame.pack(fill=tk.BOTH, expand=True)

        self.languages_listbox = tk.Listbox(lang_frame, height=8)
        self.languages_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0,5))
        self.languages_listbox.bind('<<ListboxSelect>>', self.on_language_select)

        lang_btn_frame = tk.Frame(lang_frame, bg='#ffffff')
        lang_btn_frame.pack(side=tk.RIGHT, fill=tk.Y)
        tk.Button(lang_btn_frame, text="➕", command=self.add_language, width=3).pack(pady=2)
        tk.Button(lang_btn_frame, text="✏️", command=self.edit_language, width=3).pack(pady=2)
        tk.Button(lang_btn_frame, text="🗑️", command=self.delete_language, width=3).pack(pady=2)

        # Form
        self.language_form_frame = tk.Frame(frame, bg='#ffffff')
        self.language_form_frame.pack(fill=tk.X, pady=10)

        tk.Label(self.language_form_frame, text="Langue*:", bg='#ffffff').grid(row=0, column=0, sticky='e', pady=2, padx=5)
        self.language_name_var = tk.StringVar()
        tk.Entry(self.language_form_frame, textvariable=self.language_name_var, width=25).grid(row=0, column=1, pady=2, padx=5)

        tk.Label(self.language_form_frame, text="Niveau:", bg='#ffffff').grid(row=1, column=0, sticky='e', pady=2, padx=5)
        self.language_level = ttk.Combobox(self.language_form_frame, values=["Débutant", "Intermédiaire", "Avancé", "Courant"], state="readonly", width=22)
        self.language_level.set("Intermédiaire")
        self.language_level.grid(row=1, column=1, pady=2, padx=5)

        tk.Button(self.language_form_frame, text="💾 Sauvegarder", command=self.save_language,
                 bg='#27ae60', fg='white').grid(row=2, column=1, pady=10)

    def add_language(self):
        self.language_name_var.set('')
        self.language_level.set('Intermédiaire')
        self.editing_language_index = None
        self.sections_notebook.select(4)

    def edit_language(self):
        sel = self.languages_listbox.curselection()
        if not sel:
            messagebox.showwarning("Attention", "Sélectionnez une langue à modifier")
            return
        idx = sel[0]
        lang = self.languages_data[idx]
        self.editing_language_index = idx
        self.language_name_var.set(lang.get('name',''))
        self.language_level.set(lang.get('level','Intermédiaire'))
        self.sections_notebook.select(4)

    def delete_language(self):
        sel = self.languages_listbox.curselection()
        if not sel:
            messagebox.showwarning("Attention", "Sélectionnez une langue à supprimer")
            return
        idx = sel[0]
        if messagebox.askyesno("Confirmation", "Supprimer cette langue ?"):
            del self.languages_data[idx]
            self.refresh_languages_list()
            self.update_preview()

    def save_language(self):
        name = self.language_name_var.get().strip()
        level = self.language_level.get().strip()
        if not name:
            messagebox.showerror("Erreur", "Veuillez entrer le nom de la langue")
            return
        entry = {"name": name, "level": level}
        if self.editing_language_index is None:
            self.languages_data.insert(0, entry)
        else:
            self.languages_data[self.editing_language_index] = entry
            self.editing_language_index = None
        self.refresh_languages_list()
        self.update_preview()
        messagebox.showinfo("Succès", "Langue sauvegardée")

    def refresh_languages_list(self):
        self.languages_listbox.delete(0, tk.END)
        for l in self.languages_data:
            self.languages_listbox.insert(tk.END, f"{l.get('name')} ({l.get('level')})")

    def on_language_select(self, event=None):
        sel = self.languages_listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        l = self.languages_data[idx]
        preview_text = f"{l.get('name')} - {l.get('level')}"
        self.preview_canvas.delete("all")
        self.preview_canvas.create_text(10, 10, anchor='nw', text=preview_text, font=("Arial", 10), fill="black")

    # -----------------------
    # Skills Tab (global)
    # -----------------------
    def setup_skills_tab(self):
        """Configure l'onglet de gestion des compétences"""
        frame = tk.Frame(self.skills_tab, bg='#ffffff', padx=20, pady=20)
        frame.pack(fill=tk.BOTH, expand=True)

        tk.Label(frame, text="🎯 Gestion des Compétences", font=self.subtitle_font,
                 bg='#ffffff').pack(pady=10)

        # Search and add
        search_frame = tk.Frame(frame, bg='#ffffff')
        search_frame.pack(fill=tk.X, pady=10)

        tk.Label(search_frame, text="Rechercher:", bg='#ffffff').pack(side=tk.LEFT)
        self.skill_search = tk.Entry(search_frame, width=30)
        self.skill_search.pack(side=tk.LEFT, padx=5)
        self.skill_search.bind('<KeyRelease>', self.filter_skills)

        # Skills list
        list_frame = tk.Frame(frame, bg='#ffffff')
        list_frame.pack(fill=tk.BOTH, expand=True, pady=10)

        self.skills_listbox = tk.Listbox(list_frame, height=15)
        self.skills_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))

        # Level selection
        level_frame = tk.Frame(list_frame, bg='#ffffff')
        level_frame.pack(side=tk.RIGHT, fill=tk.Y)

        tk.Label(level_frame, text="Niveau:", bg='#ffffff').pack()
        self.skill_level = ttk.Combobox(level_frame, values=["Débutant", "Intermédiaire", "Avancé", "Expert"],
                                       state="readonly", width=12)
        self.skill_level.set("Intermédiaire")
        self.skill_level.pack(pady=5)

        tk.Label(level_frame, text="Expérience (ans):", bg='#ffffff').pack()
        self.skill_experience = tk.Spinbox(level_frame, from_=0, to=50, width=5)
        self.skill_experience.pack(pady=5)

        tk.Button(level_frame, text="➕ Ajouter", command=self.add_user_skill,
                 bg='#27ae60', fg='white').pack(pady=10)

        # User skills
        user_skills_frame = tk.Frame(frame, bg='#ffffff')
        user_skills_frame.pack(fill=tk.BOTH, expand=True, pady=10)

        tk.Label(user_skills_frame, text="Mes Compétences:", bg='#ffffff').pack(anchor='w')

        self.user_skills_tree = ttk.Treeview(user_skills_frame, columns=('level', 'experience'), height=8)
        self.user_skills_tree.heading('#0', text='Compétence')
        self.user_skills_tree.heading('level', text='Niveau')
        self.user_skills_tree.heading('experience', text='Expérience (ans)')
        self.user_skills_tree.column('#0', width=200)
        self.user_skills_tree.column('level', width=100)
        self.user_skills_tree.column('experience', width=100)
        self.user_skills_tree.pack(fill=tk.BOTH, expand=True)

        # Buttons for user skills
        user_btn_frame = tk.Frame(user_skills_frame, bg='#ffffff')
        user_btn_frame.pack(fill=tk.X, pady=5)

        tk.Button(user_btn_frame, text="✏️ Modifier", command=self.edit_user_skill,
                 bg='#3498db', fg='white').pack(side=tk.LEFT, padx=5)
        tk.Button(user_btn_frame, text="🗑️ Supprimer", command=self.delete_user_skill,
                 bg='#e74c3c', fg='white').pack(side=tk.LEFT, padx=5)

        # Load initial predefined skills
        self.filter_skills()

    def filter_skills(self, event=None):
        """Filtre la liste des compétences"""
        search_term = self.skill_search.get().lower() if hasattr(self, 'skill_search') else ''
        self.skills_listbox.delete(0, tk.END)

        for skill in self.predefined_skills:
            if search_term in skill.lower():
                self.skills_listbox.insert(tk.END, skill)

    def add_user_skill(self):
        """Ajoute une compétence à l'utilisateur"""
        if not self.current_user:
            messagebox.showwarning("Attention", "Connectez-vous pour ajouter des compétences")
            return

        selection = self.skills_listbox.curselection()
        if not selection:
            messagebox.showwarning("Attention", "Veuillez sélectionner une compétence")
            return

        skill_name = self.skills_listbox.get(selection[0])
        level = self.skill_level.current() + 1
        experience = int(self.skill_experience.get())

        try:
            # Récupérer l'ID de la compétence
            self.cursor.execute('SELECT id FROM skills WHERE name = ?', (skill_name,))
            r = self.cursor.fetchone()
            if r:
                skill_id = r[0]
            else:
                # insérer si introuvable
                self.cursor.execute('INSERT INTO skills (name) VALUES (?)', (skill_name,))
                self.conn.commit()
                skill_id = self.cursor.lastrowid

            # Ajouter ou mettre à jour la compétence utilisateur
            self.cursor.execute('''
                INSERT OR REPLACE INTO user_skills (user_id, skill_id, level, experience_years)
                VALUES (?, ?, ?, ?)
            ''', (self.current_user['id'], skill_id, level, experience))

            self.conn.commit()
            self.load_user_skills()
            messagebox.showinfo("Succès", f"Compétence '{skill_name}' ajoutée!")

        except sqlite3.Error as e:
            messagebox.showerror("Erreur", f"Erreur ajout compétence: {e}")

    def edit_user_skill(self):
        """Modifie la compétence utilisateur sélectionnée (popup simple)"""
        sel = self.user_skills_tree.selection()
        if not sel:
            messagebox.showwarning("Attention", "Sélectionnez une compétence utilisateur")
            return
        skill_name = self.user_skills_tree.item(sel[0])['text']
        # récupère niv et exp actuels
        cur_values = self.user_skills_tree.item(sel[0])['values']
        cur_level = cur_values[0] if cur_values else "Intermédiaire"
        cur_exp = int(cur_values[1].split()[0]) if cur_values and cur_values[1] else 0

        # Simpledialog pour modifier
        new_level = simpledialog.askstring("Modifier niveau", f"Nouveau niveau pour {skill_name} (Débutant/Intermédiaire/Avancé/Expert):", initialvalue=cur_level)
        if new_level is None:
            return
        try:
            new_exp = int(simpledialog.askstring("Modifier expérience", "Années d'expérience:", initialvalue=str(cur_exp)))
        except:
            new_exp = cur_exp

        # écrire en base
        try:
            # récupérer skill_id
            self.cursor.execute('SELECT id FROM skills WHERE name = ?', (skill_name,))
            r = self.cursor.fetchone()
            if not r:
                messagebox.showerror("Erreur", "Compétence introuvable en base")
                return
            skill_id = r[0]
            level_index = ["Débutant", "Intermédiaire", "Avancé", "Expert"].index(new_level) + 1 if new_level in ["Débutant", "Intermédiaire", "Avancé", "Expert"] else 2
            self.cursor.execute('''
                INSERT OR REPLACE INTO user_skills (user_id, skill_id, level, experience_years)
                VALUES (?, ?, ?, ?)
            ''', (self.current_user['id'], skill_id, level_index, new_exp))
            self.conn.commit()
            self.load_user_skills()
            messagebox.showinfo("Succès", "Compétence mise à jour")
        except sqlite3.Error as e:
            messagebox.showerror("Erreur", f"Erreur mise à jour compétence: {e}")

    # -----------------------
    # User management functions
    # -----------------------
    def login(self):
        """Gère la connexion"""
        email = self.login_email.get().strip()
        password = self.login_password.get().strip()

        if not email or not password:
            messagebox.showerror("Erreur", "Veuillez remplir tous les champs")
            return

        try:
            password_hash = self.hash_password(password)
            self.cursor.execute('SELECT id, first_name, last_name, role FROM users WHERE email = ? AND password_hash = ? AND is_active = 1',
                                (email, password_hash))
            user = self.cursor.fetchone()

            if user:
                self.current_user = {
                    'id': user[0],
                    'first_name': user[1],
                    'last_name': user[2],
                    'role': user[3],
                    'email': email
                }

                # Mettre à jour la dernière connexion
                self.cursor.execute('UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = ?', (user[0],))
                self.conn.commit()

                # Mettre à jour l'interface
                self.update_user_info()
                self.load_user_cvs()
                self.load_user_skills()

                # Afficher les onglets appropriés
                self.notebook.tab(2, state='normal')  # Dashboard
                self.notebook.tab(3, state='normal')  # Editor
                self.notebook.tab(4, state='normal')  # Skills
                # masquer login/register
                try:
                    self.notebook.hide(0)  # Cacher login
                    self.notebook.hide(1)  # Cacher register
                except Exception:
                    pass
                self.notebook.select(2)  # Afficher dashboard

                messagebox.showinfo("Succès", f"Bienvenue {user[1]} {user[2]}!")
            else:
                messagebox.showerror("Erreur", "Email ou mot de passe incorrect")

        except sqlite3.Error as e:
            messagebox.showerror("Erreur", f"Erreur de connexion: {e}")

    def register(self):
        """Gère l'inscription"""
        # Récupérer les données du formulaire
        first_name = self.register_vars['register_first_name'].get().strip()
        last_name = self.register_vars['register_last_name'].get().strip()
        email = self.register_vars['register_email'].get().strip()
        password = self.register_vars['register_password'].get()
        confirm = self.register_vars['register_confirm'].get()
        role = self.register_role.get()

        # Validation
        if not all([first_name, last_name, email, password, confirm]):
            messagebox.showerror("Erreur", "Veuillez remplir tous les champs obligatoires")
            return

        if password != confirm:
            messagebox.showerror("Erreur", "Les mots de passe ne correspondent pas")
            return

        if len(password) < 6:
            messagebox.showerror("Erreur", "Le mot de passe doit faire au moins 6 caractères")
            return

        try:
            # Vérifier si l'email existe déjà
            self.cursor.execute('SELECT id FROM users WHERE email = ?', (email,))
            if self.cursor.fetchone():
                messagebox.showerror("Erreur", "Cet email est déjà utilisé")
                return

            # Hasher le mot de passe
            password_hash = self.hash_password(password)

            # Insérer l'utilisateur
            self.cursor.execute('INSERT INTO users (email, password_hash, first_name, last_name, role) VALUES (?, ?, ?, ?, ?)',
                                (email, password_hash, first_name, last_name, role))
            self.conn.commit()

            messagebox.showinfo("Succès", "Compte créé avec succès! Vous pouvez maintenant vous connecter.")
            self.notebook.select(0)  # Retour à la connexion

        except sqlite3.Error as e:
            messagebox.showerror("Erreur", f"Erreur lors de la création du compte: {e}")

    def forgot_password(self):
        """Gère la récupération de mot de passe — placeholder"""
        email = simpledialog.askstring("Mot de passe oublié", "Entrez votre email:")
        if email:
            # Ici vous implémenteriez l'envoi d'email de réinitialisation
            messagebox.showinfo("Info", "Un email de réinitialisation a été envoyé si l'adresse existe dans notre système.")

    def update_user_info(self):
        """Met à jour l'affichage des informations utilisateur"""
        for widget in self.user_info_frame.winfo_children():
            widget.destroy()

        if self.current_user:
            welcome_text = f"👋 {self.current_user['first_name']} {self.current_user['last_name']}"
            tk.Label(self.user_info_frame, text=welcome_text, bg='#2c3e50', fg='white').pack(side=tk.LEFT, padx=5)

            tk.Button(self.user_info_frame, text="Déconnexion", command=self.logout,
                     bg='#e74c3c', fg='white').pack(side=tk.LEFT, padx=5)

    def logout(self):
        """Déconnecte l'utilisateur"""
        self.current_user = None
        self.current_cv_id = None

        # Réinitialiser l'interface: masquer onglets privés et revenir au login
        try:
            self.notebook.hide(2)
            self.notebook.hide(3)
            self.notebook.hide(4)
        except Exception:
            pass

        # ré-afficher login & register si cachés
        # note: si on a supprimé les tabs initialement, on ne les ajoute pas ici — on se contente de sélectionner 0
        try:
            self.notebook.select(0)
        except Exception:
            pass

        # Nettoyer les champs
        try:
            self.login_email.delete(0, tk.END)
            self.login_password.delete(0, tk.END)
        except Exception:
            pass

    # -----------------------
    # CV management
    # -----------------------
    def load_user_cvs(self):
        """Charge les CVs de l'utilisateur et stocke correctement les IDs"""
        self.cv_listbox.delete(0, tk.END)
        self.cv_ids = []

        if self.current_user:
            try:
                self.cursor.execute('SELECT id, title, created_at FROM cvs WHERE user_id = ? ORDER BY updated_at DESC',
                                    (self.current_user['id'],))
                cvs = self.cursor.fetchall()

                for cv_id, title, created_at in cvs:
                    display_title = f"{title} ({created_at[:10]})" if created_at else title
                    self.cv_listbox.insert(tk.END, display_title)
                    self.cv_ids.append(cv_id)

            except sqlite3.Error as e:
                messagebox.showerror("Erreur", f"Erreur chargement CVs: {e}")

    def on_cv_select(self, event):
        """Gère la sélection d'un CV"""
        selection = self.cv_listbox.curselection()
        if selection and self.cv_ids:
            idx = selection[0]
            if idx < len(self.cv_ids):
                cv_id = self.cv_ids[idx]
                self.load_cv_data(cv_id)

    def load_cv_data(self, cv_id):
        """Charge les données d'un CV spécifique"""
        try:
            self.cursor.execute('SELECT data, photo_path, template FROM cvs WHERE id = ?', (cv_id,))
            row = self.cursor.fetchone()

            if not row:
                messagebox.showerror("Erreur", "CV introuvable en base")
                return

            data_json, photo_path, template = row
            data = json.loads(data_json) if data_json else {}

            self.current_cv_id = cv_id
            self.photo_path = photo_path
            self.template_var.set(template or 'classic')

            # Remplir les champs du formulaire - personnel
            personal_data = data.get('personal', {})
            # keys in personal_vars are like 'personal_first_name' -> remove prefix to get key name
            for key, var in self.personal_vars.items():
                clean_key = key.replace('personal_', '')
                var.set(personal_data.get(clean_key, ''))

            if 'description' in personal_data:
                self.personal_description.delete(1.0, tk.END)
                self.personal_description.insert(1.0, personal_data.get('description', ''))

            # expériences
            self.experience_data = data.get('experience', [])
            self.refresh_experience_list()

            # education
            self.education_data = data.get('education', [])
            try:
                self.refresh_education_list()
            except Exception:
                pass

            # skills
            self.skills_data = data.get('skills', [])
            # languages
            self.languages_data = data.get('languages', [])
            self.refresh_languages_list()

            # Charger l'image
            self.load_photo()

            # Mettre à jour les statistiques
            self.update_stats(cv_id)

            # Basculer vers l'éditeur
            self.notebook.select(3)
            self.update_preview()

        except sqlite3.Error as e:
            messagebox.showerror("Erreur", f"Erreur chargement CV: {e}")

    def new_cv(self):
        """Crée un nouveau CV"""
        if not self.current_user:
            messagebox.showwarning("Attention", "Connectez-vous pour créer un CV")
            return

        title = simpledialog.askstring("Nouveau CV", "Nommez votre CV:")
        if title:
            try:
                # Données par défaut
                default_data = {
                    'personal': {
                        'first_name': self.current_user.get('first_name', ''),
                        'last_name': self.current_user.get('last_name', ''),
                        'email': self.current_user.get('email', '')
                    },
                    'experience': [],
                    'education': [],
                    'skills': [],
                    'languages': []
                }

                self.cursor.execute('INSERT INTO cvs (user_id, title, data, template) VALUES (?, ?, ?, ?)',
                                    (self.current_user['id'], title, json.dumps(default_data), self.current_template))
                self.conn.commit()

                # Recharger la liste
                self.load_user_cvs()

                # Charger le nouveau CV
                new_id = self.cursor.lastrowid
                self.load_cv_data(new_id)

            except sqlite3.Error as e:
                messagebox.showerror("Erreur", f"Erreur création CV: {e}")

    def delete_cv(self):
        """Supprime le CV sélectionné"""
        sel = self.cv_listbox.curselection()
        if not sel:
            messagebox.showwarning("Attention", "Sélectionnez un CV à supprimer")
            return
        idx = sel[0]
        if idx >= len(self.cv_ids):
            messagebox.showerror("Erreur", "Sélection invalide")
            return
        cv_id = self.cv_ids[idx]
        if not messagebox.askyesno("Confirmation", "Voulez-vous vraiment supprimer ce CV ?"):
            return
        try:
            # récupérer chemin photo pour suppression
            self.cursor.execute('SELECT photo_path FROM cvs WHERE id = ?', (cv_id,))
            row = self.cursor.fetchone()
            if row and row[0]:
                try:
                    if os.path.exists(row[0]):
                        os.remove(row[0])
                except Exception:
                    pass

            # supprimer en base
            self.cursor.execute('DELETE FROM cvs WHERE id = ?', (cv_id,))
            self.conn.commit()

            # retirer de la liste et rafraîchir
            self.load_user_cvs()
            # si on supprimait le CV courant, nettoyer
            if self.current_cv_id == cv_id:
                self.current_cv_id = None
                self.clear_all_forms()
                self.update_preview()

            messagebox.showinfo("Succès", "CV supprimé")
        except sqlite3.Error as e:
            messagebox.showerror("Erreur", f"Erreur suppression CV: {e}")

    # -----------------------
    # Save / Export
    # -----------------------
    def save_cv(self, autosave=False):
        """Sauvegarde le CV actuel"""
        if not self.current_cv_id:
            if not autosave:
                messagebox.showerror("Erreur", "Aucun CV sélectionné")
            return

        try:
            # Récupérer les données du formulaire
            data = {
                'personal': {},
                'experience': self.experience_data,
                'education': self.education_data,
                'skills': self.skills_data,
                'languages': self.languages_data
            }

            for key, var in self.personal_vars.items():
                clean_key = key.replace('personal_', '')
                data['personal'][clean_key] = var.get()

            data['personal']['description'] = self.personal_description.get(1.0, tk.END).strip()

            # Sauvegarder la photo_path et template aussi
            photo = self.photo_path
            template = self.template_var.get()

            # Sauvegarder dans la base
            self.cursor.execute('UPDATE cvs SET data = ?, updated_at = CURRENT_TIMESTAMP, photo_path = ?, template = ? WHERE id = ?',
                                (json.dumps(data), photo, template, self.current_cv_id))
            self.conn.commit()

            # Sauvegarder l'historique
            self.cursor.execute('INSERT INTO cv_history (cv_id, data) VALUES (?, ?)',
                                (self.current_cv_id, json.dumps(data)))
            self.conn.commit()

            if not autosave:
                messagebox.showinfo("Succès", "CV sauvegardé avec succès!")

            # Mettre à jour la liste des CVs (titre peut changer)
            self.load_user_cvs()
        except sqlite3.Error as e:
            if not autosave:
                messagebox.showerror("Erreur", f"Erreur sauvegarde CV: {e}")

    def export_pdf(self):
        """Exporte le CV en PDF (implémentation simple)"""
        if not self.current_cv_id:
            messagebox.showerror("Erreur", "Aucun CV sélectionné")
            return

        try:
            # Récupérer les données
            self.cursor.execute('SELECT data FROM cvs WHERE id = ?', (self.current_cv_id,))
            row = self.cursor.fetchone()
            if not row:
                messagebox.showerror("Erreur", "CV introuvable")
                return
            cv_data = json.loads(row[0])

            # Créer le PDF minimal
            pdf = FPDF()
            pdf.add_page()
            pdf.set_font("Arial", size=16)
            personal = cv_data.get('personal', {})
            name = f"{personal.get('first_name','')} {personal.get('last_name','')}".strip()
            pdf.cell(0, 10, name, ln=True)
            pdf.set_font("Arial", size=12)
            pdf.multi_cell(0, 6, personal.get('description',''))

            # expériences
            pdf.set_font("Arial", 'B', 12)
            pdf.cell(0, 8, "Expériences", ln=True)
            pdf.set_font("Arial", size=11)
            for exp in cv_data.get('experience', []):
                pdf.cell(0, 6, f"{exp.get('position','')} - {exp.get('company','')}", ln=True)
                pdf.multi_cell(0, 5, exp.get('description',''))

            filename = filedialog.asksaveasfilename(
                defaultextension=".pdf",
                filetypes=[("PDF files", "*.pdf")],
                title="Exporter en PDF"
            )

            if filename:
                pdf.output(filename)
                messagebox.showinfo("Succès", f"CV exporté en PDF: {filename}")

        except Exception as e:
            messagebox.showerror("Erreur", f"Erreur export PDF: {e}")

    def export_word(self):
        """Exporte le CV en Word - placeholder simple (export .txt renamed .docx possible)"""
        if not self.current_cv_id:
            messagebox.showerror("Erreur", "Aucun CV sélectionné")
            return

        try:
            self.cursor.execute('SELECT data FROM cvs WHERE id = ?', (self.current_cv_id,))
            row = self.cursor.fetchone()
            if not row:
                messagebox.showerror("Erreur", "CV introuvable")
                return
            cv_data = json.loads(row[0])

            # Assembly simple en texte
            lines = []
            p = cv_data.get('personal', {})
            lines.append(f"{p.get('first_name','')} {p.get('last_name','')}")
            lines.append(p.get('description',''))
            lines.append("\nExpériences:")
            for exp in cv_data.get('experience', []):
                lines.append(f"- {exp.get('position','')} at {exp.get('company','')} ({exp.get('start_date','')} - {exp.get('end_date','') or 'Présent'})")
                if exp.get('description'):
                    lines.append(f"  {exp.get('description')}")
            # sauvegarde en .docx simple (en réalité texte)
            filename = filedialog.asksaveasfilename(
                defaultextension=".docx",
                filetypes=[("Word files", "*.docx"), ("Text files", "*.txt")],
                title="Exporter en Word (simple)"
            )
            if filename:
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write("\n".join(lines))
                messagebox.showinfo("Succès", f"CV exporté: {filename}")
        except Exception as e:
            messagebox.showerror("Erreur", f"Erreur export Word: {e}")

    # -----------------------
    # Photo upload / preview
    # -----------------------
    def upload_photo(self):
        """Upload une photo de profil"""
        if not self.current_user:
            messagebox.showwarning("Attention", "Connectez-vous pour uploader une photo")
            return

        filename = filedialog.askopenfilename(
            title="Choisir une photo",
            filetypes=[("Images", "*.png *.jpg *.jpeg *.gif *.bmp")]
        )

        if filename:
            try:
                # Compresser et redimensionner l'image
                img = Image.open(filename)
                img = ImageOps.fit(img, (200, 200), Image.LANCZOS)

                # Sauvegarder dans le dossier uploads
                timestamp = int(datetime.datetime.now().timestamp())
                photo_filename = f"user_{self.current_user['id']}_{timestamp}.jpg"
                photo_path = os.path.join("uploads", photo_filename)
                img.save(photo_path, "JPEG", quality=85)

                self.photo_path = photo_path
                self.load_photo()

                # Mettre à jour la base si CV courant
                if self.current_cv_id:
                    self.cursor.execute('UPDATE cvs SET photo_path = ? WHERE id = ?',
                                        (photo_path, self.current_cv_id))
                    self.conn.commit()

                messagebox.showinfo("Succès", "Photo uploadée")

            except Exception as e:
                messagebox.showerror("Erreur", f"Erreur traitement image: {e}")

    def load_photo(self):
        """Charge la photo actuelle"""
        if self.photo_path and os.path.exists(self.photo_path):
            try:
                img = Image.open(self.photo_path)
                img = img.resize((100, 100), Image.LANCZOS)
                photo = ImageTk.PhotoImage(img)
                self.photo_label.config(image=photo, text="")
                self.photo_label.image = photo
            except Exception:
                self.photo_label.config(image=None, text="📷 Erreur chargement")
        else:
            self.photo_label.config(image=None, text="📷 Aucune photo")

    # -----------------------
    # Stats
    # -----------------------
    def update_stats(self, cv_id):
        """Met à jour les statistiques d'un CV"""
        try:
            self.cursor.execute('SELECT view_count FROM cvs WHERE id = ?', (cv_id,))
            row = self.cursor.fetchone()
            view_count = row[0] if row else 0

            self.cursor.execute('''
                SELECT COUNT(DISTINCT viewer_id) as unique_viewers 
                FROM cv_views WHERE cv_id = ?
            ''', (cv_id,))
            unique_viewers = self.cursor.fetchone()[0]

            self.cursor.execute('''
                SELECT MAX(viewed_at) as last_view 
                FROM cv_views WHERE cv_id = ?
            ''', (cv_id,))
            last_view = self.cursor.fetchone()[0]

            stats_text = f"""Vues totales: {view_count}
Visiteurs uniques: {unique_viewers}
Dernière vue: {last_view[:10] if last_view else 'Jamais'}"""

            self.stats_label.config(text=stats_text)

        except sqlite3.Error as e:
            self.stats_label.config(text="Erreur chargement statistiques")

    # -----------------------
    # Load user skills
    # -----------------------
    def load_user_skills(self):
        """Charge les compétences de l'utilisateur"""
        if not self.current_user:
            return

        try:
            self.user_skills_tree.delete(*self.user_skills_tree.get_children())

            self.cursor.execute('''
                SELECT s.name, us.level, us.experience_years 
                FROM user_skills us
                JOIN skills s ON us.skill_id = s.id
                WHERE us.user_id = ?
                ORDER BY us.level DESC, us.experience_years DESC
            ''', (self.current_user['id'],))

            for skill_name, level, experience in self.cursor.fetchall():
                lvl_index = max(1, min(level, 4))
                level_text = ["Débutant", "Intermédiaire", "Avancé", "Expert"][lvl_index-1]
                self.user_skills_tree.insert('', 'end', text=skill_name,
                                            values=(level_text, f"{experience} ans"))

        except sqlite3.Error as e:
            messagebox.showerror("Erreur", f"Erreur chargement compétences: {e}")

    def delete_user_skill(self):
        """Supprime une compétence utilisateur"""
        selection = self.user_skills_tree.selection()
        if not selection:
            messagebox.showwarning("Attention", "Veuillez sélectionner une compétence")
            return

        skill_name = self.user_skills_tree.item(selection[0])['text']

        if messagebox.askyesno("Confirmation", f"Supprimer la compétence '{skill_name}'?"):
            try:
                self.cursor.execute('''
                    DELETE FROM user_skills 
                    WHERE user_id = ? AND skill_id = (
                        SELECT id FROM skills WHERE name = ?
                    )
                ''', (self.current_user['id'], skill_name))

                self.conn.commit()
                self.load_user_skills()

            except sqlite3.Error as e:
                messagebox.showerror("Erreur", f"Erreur suppression compétence: {e}")

    # -----------------------
    # Preview / UI helpers
    # -----------------------
    def update_preview(self, event=None):
        """Met à jour l'aperçu en direct (rendu texte simple)"""
        self.preview_canvas.delete("all")
        lines = []
        # Personal
        first = self.personal_vars.get('personal_first_name').get() if 'personal_first_name' in self.personal_vars else ''
        last = self.personal_vars.get('personal_last_name').get() if 'personal_last_name' in self.personal_vars else ''
        title = self.personal_vars.get('personal_title').get() if 'personal_title' in self.personal_vars else ''
        email = self.personal_vars.get('personal_email').get() if 'personal_email' in self.personal_vars else ''
        desc = self.personal_description.get(1.0, tk.END).strip()

        lines.append(f"{first} {last}")
        if title:
            lines.append(title)
        if email:
            lines.append(email)
        if desc:
            lines.append("")
            lines.append(desc[:500])

        lines.append("\nExpériences:")
        for exp in self.experience_data[:5]:
            lines.append(f"- {exp.get('position','')} at {exp.get('company','')} ({exp.get('start_date','')} - {exp.get('end_date','') or 'Présent'})")

        lines.append("\nFormations:")
        for ed in self.education_data[:5]:
            lines.append(f"- {ed.get('degree','')} - {ed.get('school','')} ({ed.get('start_year','')})")

        lines.append("\nCompétences:")
        if isinstance(self.skills_data, list):
            lines.append(", ".join(self.skills_data[:20]))
        else:
            lines.append("")

        lines.append("\nLangues:")
        for l in self.languages_data[:5]:
            lines.append(f"- {l.get('name')} ({l.get('level')})")

        # draw text
        text = "\n".join(lines)
        self.preview_canvas.create_text(10, 10, anchor='nw', text=text, font=("Arial", 10), fill="black")

    def clear_all_forms(self):
        """Réinitialise tous les formulaires"""
        for v in self.personal_vars.values():
            v.set('')
        self.personal_description.delete(1.0, tk.END)
        self.experience_data = []
        self.refresh_experience_list()
        self.education_data = []
        try:
            self.refresh_education_list()
        except Exception:
            pass
        self.skills_data = []
        self.languages_data = []
        self.refresh_languages_list()
        self.photo_path = None
        self.load_photo()

    # -----------------------
    # Autosave
    # -----------------------
    def setup_autosave(self):
        """Configure la sauvegarde automatique"""
        def autosave():
            try:
                if self.current_user and self.current_cv_id:
                    self.save_cv(autosave=True)
            except Exception:
                pass
            # relancer
            self.root.after(30000, autosave)  # Toutes les 30 secondes

        # démarrer la boucle après 30s
        self.root.after(30000, autosave)
        
 
    def change_template(self, event=None):
        """
        Change le modèle de CV en fonction de la sélection.
        Pour l'instant c'est une version de démonstration.
        """
        if hasattr(self, "template_var"):
            selected_template = self.template_var.get()
            print(f"[DEBUG] Nouveau modèle choisi : {selected_template}")
            messagebox.showinfo("Template", f"Modèle sélectionné : {selected_template}")
        else:
            print("[DEBUG] Aucun template sélectionné.")

        
        
        


# -----------------------
# Entrée main
# -----------------------
def main():
    root = tk.Tk()
    app = CVGeneratorApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()
