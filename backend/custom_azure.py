from storages.backends.azure_storage import AzureStorage
import os

class AzureMediaStorage(AzureStorage):
    account_name = 'umalienartifactsstorage' # Must be replaced by your <storage_account_name>
    account_key = os.environ['STORAGE_KEY']
    # account_key = 'T3fyAzfvTEK7jwh8h5gKYudcJhjFvTgnlYXMY6+aSx0A8bNuBckt0xYB7ydaLcSO1lL5nVEkq1Nv+ASt37H7fQ==' # Must be replaced by your <storage_account_key>
    azure_container = 'media'
    expiration_secs = None

class AzureStaticStorage(AzureStorage):
    account_name = 'umalienartifactsstorage' # Must be replaced by your storage_account_name
    account_key = os.environ['STORAGE_KEY']
    # account_key = 'T3fyAzfvTEK7jwh8h5gKYudcJhjFvTgnlYXMY6+aSx0A8bNuBckt0xYB7ydaLcSO1lL5nVEkq1Nv+ASt37H7fQ==' # Must be replaced by your <storage_account_key>
    azure_container = 'static'
    expiration_secs = None