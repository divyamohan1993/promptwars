$gcloudPath = "C:\Program Files (x86)\Google\Cloud SDK\google-cloud-sdk\bin"
if ($env:Path -notlike "*$gcloudPath*") {
    $env:Path += ";$gcloudPath"
    Write-Host "Added gcloud temporarily to PATH for this session."
}

if (Get-Command gcloud -ErrorAction SilentlyContinue) {
    Write-Host "Verifying gcloud configuration..."
    gcloud auth list
    gcloud config list
    
    Write-Host "`nSetting up project dmjone..."
    gcloud config set project dmjone
    gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com
    
    Write-Host "`nSetup complete! You may need to restart your terminal for global PATH changes to take effect."
} else {
    Write-Host "Error: gcloud command still not found. Please restart your terminal."
}
