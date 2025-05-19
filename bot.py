import discord
from discord.ext import commands, tasks
import requests
from bs4 import BeautifulSoup
import json
import os

TOKEN = os.getenv("TOKEN")

INTENTS = discord.Intents.default()
INTENTS.message_content = True
INTENTS.guilds = True
INTENTS.members = True
bot = commands.Bot(command_prefix="/", intents=INTENTS)

DATA_FILE = "recherches.json"

def charger_recherches():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return {}

def sauvegarder_recherches(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

recherches = charger_recherches()

@bot.command()
async def ajouter_recherche(ctx, categorie, *, mots_cles):
    user_id = str(ctx.author.id)
    if user_id not in recherches:
        recherches[user_id] = []
    recherches[user_id].append({"categorie": categorie, "mots_cles": mots_cles})
    sauvegarder_recherches(recherches)
    await ctx.send(f"🔍 Recherche ajoutée pour {ctx.author.mention} : `{categorie}` - `{mots_cles}`")

@bot.command()
async def supprimer_recherche(ctx, index: int):
    user_id = str(ctx.author.id)
    if user_id in recherches and 0 <= index < len(recherches[user_id]):
        supprimee = recherches[user_id].pop(index)
        sauvegarder_recherches(recherches)
        await ctx.send(f"❌ Recherche supprimée : `{supprimee['categorie']}` - `{supprimee['mots_cles']}`")
    else:
        await ctx.send("❗ Index invalide.")

@bot.command()
async def voir_recherches(ctx):
    user_id = str(ctx.author.id)
    if user_id in recherches and recherches[user_id]:
        msg = "📋 Vos recherches :\n"
        for i, r in enumerate(recherches[user_id]):
            msg += f"`{i}` - {r['categorie']} : {r['mots_cles']}\n"
        await ctx.send(msg)
    else:
        await ctx.send("🔎 Aucune recherche enregistrée.")

def chercher_leboncoin(mot_cle, categorie):
    cat_code = "26" if categorie == "carte" else "2"
    url = f"https://www.leboncoin.fr/recherche?category={cat_code}&text={mot_cle}"
    headers = {"User-Agent": "Mozilla/5.0"}
    r = requests.get(url, headers=headers)
    soup = BeautifulSoup(r.text, 'html.parser')
    annonces = []
    for a in soup.select("a[data-qa-id='aditem_container']")[:3]:
        titre = a.select_one("span[data-qa-id='aditem_title']")
        lien = "https://www.leboncoin.fr" + a.get("href")
        if titre:
            annonces.append({"titre": titre.text.strip(), "lien": lien})
    return annonces

def chercher_vinted(mot_cle):
    url = f"https://www.vinted.fr/catalog?search_text={mot_cle}&category_id=2071"
    headers = {"User-Agent": "Mozilla/5.0"}
    r = requests.get(url, headers=headers)
    soup = BeautifulSoup(r.text, 'html.parser')
    annonces = []
    for item in soup.find_all('a', class_='new-item-box__overlay-link')[:3]:
        titre = item.get('title')
        lien = "https://www.vinted.fr" + item.get('href')
        if titre:
            annonces.append({"titre": titre.strip(), "lien": lien})
    return annonces

async def envoyer_annonce(guild, categorie, mot_cle, resultats):
    cat_name = f"{categorie.capitalize()} - Recherche"
    cat = discord.utils.get(guild.categories, name=cat_name)
    if not cat:
        cat = await guild.create_category(cat_name)

    for res in resultats:
        salon_name = res['titre'][:90].replace(' ', '-').replace('/', '-').lower()
        salon = discord.utils.get(cat.channels, name=salon_name)
        if not salon:
            salon = await guild.create_text_channel(salon_name, category=cat)
        await salon.send(f"🛍️ {res['titre']}\n🔗 {res['lien']}")

@tasks.loop(minutes=60)
async def recherche_auto():
    for user_id, reqs in recherches.items():
        user = await bot.fetch_user(int(user_id))
        for guild in bot.guilds:
            member = guild.get_member(int(user_id))
            if not member:
                continue
            for r in reqs:
                cat = r['categorie']
                mot = r['mots_cles']
                if cat == "carte":
                    res_lbc = chercher_leboncoin(mot, cat)
                    res_vinted = chercher_vinted(mot)
                    await envoyer_annonce(guild, cat, mot, res_lbc + res_vinted)
                elif cat == "voiture":
                    res = chercher_leboncoin(mot, cat)
                    await envoyer_annonce(guild, cat, mot, res)

@bot.event
async def on_ready():
    print(f"🤖 Connecté en tant que {bot.user}")
    recherche_auto.start()

bot.run(TOKEN)