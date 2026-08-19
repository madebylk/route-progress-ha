# Contributing

Danke für dein Interesse an Route Progress for Home Assistant.

## Fehler und Vorschläge

- Nutze die passende Issue-Vorlage.
- Suche vorher nach bereits vorhandenen Issues.
- Veröffentliche keine Tokens, Freigabelinks, Standortdaten oder anderen
  persönlichen Informationen.
- Dieses Repository behandelt ausschließlich die Home-Assistant-Integration.
  Die Server-Komponente ist nicht Teil des öffentlichen Projekts.

## Pull Requests

1. Erstelle einen eigenen Branch.
2. Halte Änderungen auf ein klar beschriebenes Thema begrenzt.
3. Ergänze oder aktualisiere Tests für geändertes Verhalten.
4. Aktualisiere bei sichtbaren Textänderungen sowohl `strings.json` als auch die
   deutschen und englischen Übersetzungen.
5. Führe vor dem Pull Request die Tests aus:

   ```sh
   python -m unittest discover -s tests -v
   ```

6. Nenne im Pull Request die Motivation, die Auswirkungen und die durchgeführten
   Prüfungen.

Beiträge werden geprüft und erst nach Freigabe durch den Maintainer übernommen.

## Lizenz

Mit einem Beitrag erklärst du dich damit einverstanden, dass er unter der
MIT-Lizenz dieses Repositorys veröffentlicht wird.
