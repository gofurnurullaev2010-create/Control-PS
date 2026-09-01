@echo off
set "PATH=C:\Program Files\Git\cmd;%PATH%"
cd /d "D:\Control PS"
set FILTER_BRANCH_SQUELCH_WARNING=1
git filter-branch -f --index-filter "git rm -r --cached --ignore-unmatch vidaa" --prune-empty -- --all
echo ---- TARIXDA QOLDIMI? ----
git log --all --name-only --pretty=format: -- vidaa
echo ---- TUGADI ----
