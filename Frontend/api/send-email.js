import nodemailer from 'nodemailer';

export default async function handler(req, res) {
  // CORS Headers
  res.setHeader('Access-Control-Allow-Credentials', 'true');
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET,OPTIONS,PATCH,DELETE,POST,PUT');
  res.setHeader(
    'Access-Control-Allow-Headers',
    'X-CSRF-Token, X-Requested-With, Accept, Accept-Version, Content-Length, Content-MD5, Content-Type, Date, X-Api-Version, x-relay-secret'
  );

  // Handle CORS Preflight
  if (req.method === 'OPTIONS') {
    return res.status(200).end();
  }

  if (req.method !== 'POST') {
    return res.status(405).json({ success: false, error: 'Method Not Allowed' });
  }

  // Verify secret relay token
  const authHeader = req.headers['x-relay-secret'] || (req.body && req.body.secret);
  const EXPECTED_SECRET = 'pulsechat-secret-relay-key-2026';

  if (authHeader !== EXPECTED_SECRET) {
    return res.status(401).json({ success: false, error: 'Unauthorized: Invalid relay token' });
  }

  const { to, subject, html, text } = req.body || {};

  if (!to || !subject) {
    return res.status(400).json({ success: false, error: 'Missing required parameters: to, subject' });
  }

  const user = (process.env.SMTP_USER || 'subhanulhaq935@gmail.com').trim();
  const pass = (process.env.SMTP_PASSWORD || 'onpieqttlpqestgh').replace(/\s+/g, '').trim();

  try {
    const transporter = nodemailer.createTransport({
      host: 'smtp.gmail.com',
      port: 465,
      secure: true,
      auth: {
        user,
        pass,
      },
      tls: {
        rejectUnauthorized: true,
      },
    });

    const info = await new Promise((resolve, reject) => {
      transporter.sendMail(
        {
          from: `"PulseChat" <${user}>`,
          to,
          subject,
          text: text || '',
          html: html || '',
        },
        (err, result) => {
          if (err) {
            reject(err);
          } else {
            resolve(result);
          }
        }
      );
    });

    return res.status(200).json({
      success: true,
      messageId: info.messageId,
      deliveredTo: to,
    });
  } catch (error) {
    console.error('Nodemailer send error:', error);
    return res.status(500).json({
      success: false,
      error: error.message || 'Failed to dispatch email via Gmail SMTP',
    });
  }
}
