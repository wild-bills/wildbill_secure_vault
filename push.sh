#!/bin/bash
git remote remove origin
X="https://github.com"
Y="/wild-bills"
Z="/wildbill_secure_vault.git"
git remote add origin "$X$Y$Z"
git add .
git add database/store.db --force
git commit -m "previews"
git branch -M main
git push -u origin main --force
