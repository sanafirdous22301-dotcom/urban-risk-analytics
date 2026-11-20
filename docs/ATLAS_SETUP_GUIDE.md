# URBANRISK — MongoDB Atlas Setup & Data Transfer Guide

This guide explains how to set up a free cloud database on **MongoDB Atlas** for your **Render** deployment while keeping your local MongoDB database completely intact.

---

## Step 1: Create a Free MongoDB Atlas Account & Cluster

1. Go to [mongodb.com/atlas](https://www.mongodb.com/cloud/atlas/register) and create a free account (or log in).
2. Click **"Create a Database"** and select the **M0 Free Cluster** (Shared).
3. Choose a cloud provider and region close to your users (e.g., **AWS / Mumbai (`ap-south-1`)**).
4. Name your cluster (e.g., `Cluster0` or `urbanrisk-cluster`) and click **"Create"**.

---

## Step 2: Configure Database Security

### A. Create a Database User
1. In the **Security > Database Access** tab, click **"Add New Database User"**.
2. Authentication Method: **Password**.
3. Set a username (e.g., `urbanrisk_admin`).
4. Set a strong password (e.g., `UrbanRiskSecure2026!`). Make sure to save this password!
5. Database User Privileges: Select **"Read and write to any database"**.
6. Click **"Add User"**.

### B. Configure Network Access (Allow Render Connection)
Render free-tier web services have dynamic outbound IP addresses.
1. In the **Security > Network Access** tab, click **"Add IP Address"**.
2. Click **"Allow Access from Anywhere"** (this enters `0.0.0.0/0`).
3. Click **"Confirm"**.
*(Access is still fully protected because only users with the correct username and password can connect).*

---

## Step 3: Obtain Your Atlas Connection String

1. In the **Database > Deployments** tab, click **"Connect"** on your cluster.
2. Choose **"Drivers"** (Python).
3. Copy the SRV connection string, which looks like:
   ```text
   mongodb+srv://urbanrisk_admin:<password>@cluster0.abcde.mongodb.net/?retryWrites=true&w=majority
   ```
4. Replace `<password>` with the actual password you created in Step 2A.

---

## Step 4: Transfer Data from Local MongoDB to Atlas

Run the provided transfer utility from your project root:

```powershell
python scripts/export_to_atlas.py --atlas-uri "mongodb+srv://urbanrisk_admin:YOUR_PASSWORD@cluster0.abcde.mongodb.net/?retryWrites=true&w=majority"
```

The script will:
* Connect to your local MongoDB (`mongodb://127.0.0.1:27017/urban_risk_db`).
* Read all 9 collections (117,502 records).
* Upload them to your Atlas cluster.
* Automatically create the spatial `2dsphere` indexes on `infrastructure_assets.geom` and `road_segments.geom`.

---

## Step 5: Configure Render Environment Variables

When creating or configuring your Render Web Service:
1. Navigate to your Web Service in the Render Dashboard.
2. Go to **Environment**.
3. Add the following variables:
   * **`MONGODB_URI`**: `mongodb+srv://urbanrisk_admin:YOUR_PASSWORD@cluster0.abcde.mongodb.net/?retryWrites=true&w=majority`
   * **`MONGODB_DATABASE`**: `urban_risk_db`
4. Click **"Save Changes"**. Render will automatically redeploy and connect to Atlas!
