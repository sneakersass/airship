version_part=${1:-2}

dir="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
deploy_script=$dir/../src/deploy.py

current_version=`cat $dir/../src/deploy.py | grep -E 'version = "v.*"' | sed -E -e 's/version = |"|v//g'`

increment_version() {
  local delimiter=.
  local array=($(echo "$1" | tr $delimiter '\n'))
  array[$2]=$((array[$2]+1))
  echo $(local IFS=$delimiter ; echo "${array[*]}")
}

new_version="$(increment_version $current_version $version_part)"

read -p "New version is $new_version continue?" CONDITION;

cp $deploy_script $deploy_script"_bak"
sed "s/v$current_version/v$new_version/g" $deploy_script > $deploy_script"_new"
mv $deploy_script"_new" $deploy_script
chmod +x $deploy_script

git commit -m "Release v"$new_version $dir/../
git push

git tag "v"$new_version
git push origin "v"$new_version

